"""Verify deployed wheel provenance and actual installed file bytes, never import plugins."""

from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import re
import sysconfig

from packaging.utils import canonicalize_name

from .inspection import safe_member
from .models import (DeploymentManifest, DeploymentPackage, ExecutionPackageError,
                     MAX_FILE_BYTES, MAX_PACKAGES, RuntimeIdentity, unique_object)

MAX_DEPLOYMENT_MANIFEST_BYTES = 16 * 1024 * 1024
_IMAGE = re.compile(r"^(?=.{1,256}$)(?:[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]{1,5})?/)?[a-z0-9]+(?:[._/-][a-z0-9]+)*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|@sha256:[0-9a-f]{64})$")


def valid_image_ref(value: str | None) -> str | None:
    if value is None or not value:
        return None
    if not _IMAGE.fullmatch(value) or ".." in value or "//" in value:
        raise ExecutionPackageError("deployment_unavailable")
    return value


def verify_distribution(package: DeploymentPackage, *, distribution_lookup=metadata.distribution) -> bool:
    """Wheel RECORD is installer-modified; compare the original wheel's other members."""
    try:
        dist = distribution_lookup(package.distributionName)
        if canonicalize_name(dist.metadata["Name"]) != package.distributionName or dist.version != package.version:
            return False
        site = Path(dist.locate_file("")).resolve(strict=True)
        # The expected wheel files all remain direct children of this distribution environment.
        recorded = {str(item) for item in (dist.files or ())}
        expected = {item.path for item in package.files}
        if not 1 <= len(expected) == len(package.files) <= 512 or not expected.issubset(recorded):
            return False
        info_roots = {name.split("/")[0] for name in expected if ".dist-info/" in name}
        if len(info_roots) != 1:
            return False
        info_root = next(iter(info_roots))
        for name in recorded - expected:
            safe_member(name)
            if name in {info_root + "/RECORD", info_root + "/INSTALLER", info_root + "/REQUESTED", info_root + "/direct_url.json"}:
                continue
            if "/__pycache__/" in name and name.endswith(".pyc"):
                continue
            return False
        for item in package.files:
            safe_member(item.path)
            path = Path(dist.locate_file(item.path))
            current = path
            while current != site:
                if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                    return False
                if current == current.parent:
                    return False
                current = current.parent
            if not path.resolve(strict=True).is_relative_to(site):
                return False
            if not path.is_file() or path.stat().st_size != item.sizeBytes or item.sizeBytes > MAX_FILE_BYTES:
                return False
            with path.open("rb") as stream:
                content = stream.read(MAX_FILE_BYTES + 1)
            if sha256(content).hexdigest() != item.sha256:
                return False
        for top in {name.split("/")[0] for name in expected}:
            folder = site / top
            if not folder.is_dir():
                continue
            for path in folder.rglob("*"):
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    return False
                if path.is_file():
                    name = path.relative_to(site).as_posix()
                    if name in expected or name in {info_root + "/RECORD", info_root + "/INSTALLER", info_root + "/REQUESTED", info_root + "/direct_url.json"}:
                        continue
                    if "/__pycache__/" in name and name.endswith(".pyc"):
                        continue
                    return False
                elif not path.is_dir():
                    return False
        groups = {"loop": "agent_loops", "policy": "execution_policies"}
        if not 1 <= len(package.plugins) <= 32 or not all(plugin.apiVersion in {1, 2, 3, 4} and (plugin.apiVersion < 3 or plugin.kind == "loop") and any(
            point.group == f"opensprite_backend.{groups[plugin.kind]}.v{plugin.apiVersion}" and point.name == plugin.id and point.value == plugin.entryPoint
            for point in dist.entry_points) for plugin in package.plugins):
            return False
        return True
    except Exception:
        return False


class RuntimePackageIdentity:
    def __init__(self, *, base_image_ref=None, runtime_kind="local", manifest_path=None,
                 distribution_lookup=metadata.distribution):
        if runtime_kind not in {"local", "docker"}:
            raise ValueError("invalid runtime kind")
        self.kind = runtime_kind
        try:
            self.base_image = valid_image_ref(base_image_ref)
        except ExecutionPackageError:
            self.base_image = None
        self.manifest_path = Path(manifest_path) if manifest_path is not None else (
            Path("/app/execution-plugin-manifest.json") if runtime_kind == "docker" else None)
        self.lookup = distribution_lookup

    def snapshot(self):
        manifest = None
        status = "missing"
        if self.manifest_path is not None:
            try:
                path = self.manifest_path
                if path.exists():
                    if not path.is_file() or path.is_symlink() or (os.name != "nt" and (path.stat().st_uid != 0 or path.stat().st_mode & 0o022)):
                        raise ValueError("writable manifest")
                    with path.open("rb") as stream:
                        data = stream.read(MAX_DEPLOYMENT_MANIFEST_BYTES + 1)
                    if len(data) > MAX_DEPLOYMENT_MANIFEST_BYTES:
                        raise ValueError("oversized deployment manifest")
                    raw = json.loads(data.decode(), object_pairs_hook=unique_object)
                    if type(raw) is not dict or type(raw.get("schemaVersion")) is not int:
                        raise ValueError("invalid manifest")
                    manifest = DeploymentManifest.model_validate(raw)
                    if valid_image_ref(manifest.baseImage) is None:
                        raise ValueError("missing base image")
                    identities = {package.distributionName for package in manifest.packages}
                    if not 1 <= len(identities) == len(manifest.packages) <= MAX_PACKAGES:
                        raise ValueError("duplicate package identity")
                    plugins = [(plugin.kind, plugin.id) for package in manifest.packages for plugin in package.plugins]
                    if len(plugins) != len(set(plugins)):
                        raise ValueError("duplicate plugin identity")
                    if not all(verify_distribution(package, distribution_lookup=self.lookup) for package in manifest.packages):
                        raise ValueError("installed distribution changed")
                    status = "verified"
            except Exception:
                manifest = None
                status = "invalid"
        return RuntimeIdentity(kind=self.kind, baseImage=self.base_image, manifestStatus=status), manifest

    def package_status(self, inspection, manifest):
        if any(plugin.apiVersion != 4 or plugin.kind != "loop" for plugin in inspection.plugins):
            return "needs_update"
        try:
            dist = self.lookup(inspection.distributionName)
        except metadata.PackageNotFoundError:
            return "not_installed"
        except Exception:
            return "unverified"
        if manifest is None:
            return "unverified"
        deployed = next((package for package in manifest.packages
                         if package.distributionName == inspection.distributionName), None)
        if deployed is None:
            return "unverified"
        if deployed.version != inspection.version or deployed.sha256 != inspection.sha256 or deployed.plugins != inspection.plugins:
            return "mismatch"
        if deployed.files != inspection.files or dist.version != inspection.version:
            return "mismatch"
        return "confirmed"
