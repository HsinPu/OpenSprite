"""Export an offline Docker build context, never build or install in this process."""

from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

from .inspection import check_environment
from .models import ExecutionPackageError
from .runtime_identity import valid_image_ref

# This exported build-time verifier is repository deployment automation, not an
# application CLI. It intentionally uses only stdlib and installed packaging.
_VALIDATE = r'''"""Verify an offline wheel deployment and write root-owned image provenance."""
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

SOURCE = json.loads(SOURCE_JSON)
MANIFEST = Path("/app/execution-plugin-manifest.json")

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result

def verify(package):
    if set(package) != {"distributionName", "version", "sha256", "plugins", "files"}:
        raise ValueError("invalid package manifest")
    dist = metadata.distribution(package["distributionName"])
    if canonicalize_name(dist.metadata["Name"]) != package["distributionName"] or dist.version != package["version"]:
        raise ValueError("installed package identity mismatch")
    site = Path(dist.locate_file("")).resolve(strict=True)
    expected = {item["path"] for item in package["files"]}
    recorded = {str(item) for item in dist.files or ()}
    if not 1 <= len(expected) == len(package["files"]) <= 512 or not expected.issubset(recorded):
        raise ValueError("installed file inventory mismatch")
    roots = {path.split("/")[0] for path in expected if ".dist-info/" in path}
    if len(roots) != 1:
        raise ValueError("invalid distribution inventory")
    info = next(iter(roots))
    for path in recorded - expected:
        if path in {info + "/RECORD", info + "/INSTALLER", info + "/REQUESTED", info + "/direct_url.json"}:
            continue
        if "/__pycache__/" in path and path.endswith(".pyc"):
            continue
        raise ValueError("unexpected installed file")
    for item in package["files"]:
        name = item["path"]
        if not isinstance(name, str) or len(name) > 256 or any(
            part in {"", ".", ".."} or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}", part)
            for part in name.split("/")):
            raise ValueError("invalid installed path")
        path = Path(dist.locate_file(name))
        current = path
        while current != site:
            if current.is_symlink() or current == current.parent:
                raise ValueError("installed file link")
            current = current.parent
        if not path.resolve(strict=True).is_relative_to(site) or not 0 <= item["sizeBytes"] <= 4194304:
            raise ValueError("installed file outside environment")
        if not path.is_file() or path.stat().st_size != item["sizeBytes"]:
            raise ValueError("installed size mismatch")
        with path.open("rb") as stream:
            content = stream.read(4194305)
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError("installed content mismatch")
    for top in {name.split("/")[0] for name in expected}:
        folder = site / top
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise ValueError("installed directory link")
            if path.is_file():
                name = path.relative_to(site).as_posix()
                if name in expected or name in {info + "/RECORD", info + "/INSTALLER", info + "/REQUESTED", info + "/direct_url.json"}:
                    continue
                if "/__pycache__/" in name and name.endswith(".pyc"):
                    continue
                raise ValueError("unrecorded installed source")
            elif not path.is_dir():
                raise ValueError("nonregular installed source")
    groups = {"loop": "opensprite_backend.agent_loops.v1", "policy": "opensprite_backend.execution_policies.v1"}
    for plugin in package["plugins"]:
        if plugin["apiVersion"] != 1 or not any(point.group == groups[plugin["kind"]]
            and point.name == plugin["id"] and point.value == plugin["entryPoint"] for point in dist.entry_points):
            raise ValueError("installed entry point mismatch")

try:
    # Installation must have used these exact archive bytes.
    wheel = Path("/opt/opensprite-plugin") / SOURCE["fileName"]
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != SOURCE["sha256"]:
        raise ValueError("wheel changed")
    environment = default_environment()
    if SOURCE["requiresPython"] is not None and not SpecifierSet(SOURCE["requiresPython"]).contains(environment["python_full_version"], prereleases=True):
        raise ValueError("incompatible Python")
    for raw in SOURCE["requiresDist"]:
        requirement = Requirement(raw)
        if requirement.url or requirement.extras:
            raise ValueError("unsupported requirement")
        if requirement.marker is None or requirement.marker.evaluate(environment):
            if not requirement.specifier.contains(metadata.version(requirement.name), prereleases=True):
                raise ValueError("incompatible dependency")
    package = {key: SOURCE[key] for key in ("distributionName", "version", "sha256", "plugins", "files")}
    previous = []
    if MANIFEST.exists():
        if not MANIFEST.is_file() or MANIFEST.is_symlink() or MANIFEST.stat().st_uid != 0 or MANIFEST.stat().st_mode & 0o022:
            raise ValueError("untrusted previous manifest")
        if MANIFEST.stat().st_size > 16777216:
            raise ValueError("oversized manifest")
        old = json.loads(MANIFEST.read_text(), object_pairs_hook=unique)
        if set(old) != {"schemaVersion", "baseImage", "packages"} or type(old["schemaVersion"]) is not int or old["schemaVersion"] != 1:
            raise ValueError("invalid previous manifest")
        previous = [item for item in old["packages"] if item["distributionName"] != package["distributionName"]]
    packages = [*previous, package]
    if not 1 <= len(packages) <= 64 or len({item["distributionName"] for item in packages}) != len(packages):
        raise ValueError("duplicate deployment packages")
    plugins = [(plugin["kind"], plugin["id"]) for item in packages for plugin in item["plugins"]]
    if len(plugins) != len(set(plugins)):
        raise ValueError("duplicate deployment plugin identity")
    for item in packages:
        verify(item)
    manifest = {"schemaVersion": 1, "baseImage": BASE_IMAGE, "packages": packages}
    temporary = MANIFEST.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o644)
    os.replace(temporary, MANIFEST)
    print("Execution plugin distribution files and deployment provenance verified.")
except Exception:
    raise SystemExit("Execution plugin deployment verification failed.") from None
'''


def deployment_bundle(stored, wheel_data: bytes, base_image_ref: str | None) -> bytes:
    image = valid_image_ref(base_image_ref)
    if image is None:
        raise ExecutionPackageError("deployment_unavailable")
    inspection = stored.inspection
    check_environment(inspection.requiresPython, inspection.requiresDist)
    wheel_name = inspection.fileName
    derived_image = f"opensprite:plugin-{inspection.sha256[:16]}"
    source = json.dumps(inspection.model_dump(), separators=(",", ":"))
    validator = "SOURCE_JSON = " + repr(source) + "\nBASE_IMAGE = " + repr(image) + "\n" + _VALIDATE
    dockerfile = f'''FROM {image}
USER root
COPY {wheel_name} /opt/opensprite-plugin/{wheel_name}
COPY validate_deployment.py /opt/opensprite-plugin/validate_deployment.py
RUN /app/backend/.venv/bin/python -m ensurepip --upgrade \\
    && /app/backend/.venv/bin/python -m pip install --no-index --no-deps --force-reinstall /opt/opensprite-plugin/{wheel_name} \\
    && /app/backend/.venv/bin/python -m pip check \\
    && /app/backend/.venv/bin/python /opt/opensprite-plugin/validate_deployment.py
USER opensprite
'''
    compose = f'''services:
  opensprite:
    image: {derived_image}
    build:
      context: ${{OPENSPRITE_PLUGIN_BUNDLE_DIR:?Set the absolute extracted bundle directory}}
      dockerfile: Dockerfile
    environment:
      OPENSPRITE_RUNTIME_KIND: docker
      OPENSPRITE_DEPLOYMENT_BASE_IMAGE: {json.dumps(derived_image)}
'''
    readme = f'''# OpenSprite execution-plugin deployment

Imported distribution: {inspection.distributionName} {inspection.version}
Wheel SHA-256: {inspection.sha256}
Base image supplied by the operator: {image}
Resulting image and base for the next plugin deployment: {derived_image}

Importing a wheel did not install it. This bundle builds a derived image on the
Docker host. Review the Python package before building: plugins have backend
process privileges. Installation and validation run at build time as root;
the final application continues as the existing opensprite user.

Extract this ZIP to one directory. From that directory set its absolute path:

PowerShell:
    $env:OPENSPRITE_PLUGIN_BUNDLE_DIR = (Get-Location).Path

Bash:
    export OPENSPRITE_PLUGIN_BUNDLE_DIR="$(pwd)"

Append this override to your EXISTING compose invocation and keep its existing
project name, environment and data volume. Paths below are examples to replace:

    docker compose -f /path/to/OpenSprite/compose.yaml -f /path/to/extracted/compose.override.yaml up -d --build --wait

Compose resolves relative paths from the first compose file; the absolute bundle
environment variable avoids ambiguity. The override creates no new data volume
and does not select a new project name. Do not use down -v. Finish or cancel
active Runs before replacing the sole writer of the existing data volume.

The configured base image must be available on this Docker host; prefer a
digest-pinned reference. No package or dependency is downloaded: ensurepip uses
Python's bundled installer, then pip --no-index --no-deps and pip check verify
the installed dependency environment. A missing or incompatible dependency
fails the build. The validator checks the exact wheel hash, installed files,
entry point metadata and preserves verified unrelated deployed packages.
The override sets the restarted runtime's next deployment base to the resulting
image, so adding another plugin retains previously deployed packages. Keep that
image available on the same Docker host. Rebuilding this same wheel can use the
existing resulting tag as both its source and output; it requires the source
image to exist before the build and replaces that tag after a successful build.
Preserve a separate previous image reference before rebuilding for rollback.

After restart open the execution-plugin workbench. This wheel is confirmed
only when the build manifest and actual installed contents match its SHA-256.
Select its Loop/policy using the existing execution settings. A completed Run
does not itself prove task correctness: run your reviewed acceptance task.

For rollback use the previous compatible image and the same existing volume.
If backend/SQLite schema changed, restore a compatible stopped-service backup
instead of assuming an older backend can write the newer schema. Back up the
whole sensitive .opensprite root, including auth.json and credential.key.
Removing the imported cache entry does not uninstall the deployed plugin.
'''
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in ((wheel_name, wheel_data), ("Dockerfile", dockerfile),
            ("compose.override.yaml", compose), ("README.md", readme), ("validate_deployment.py", validator)):
            archive.writestr(name, content)
    return output.getvalue()
