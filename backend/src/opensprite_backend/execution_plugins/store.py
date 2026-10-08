"""Atomic private UUID-directory cache; deleting imports never uninstalls code."""

from datetime import UTC, datetime
import json
import os
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from opensprite_backend.app_paths import AppPaths
from opensprite_backend.atomic_file import atomic_write

from .inspection import inspect_wheel
from .models import (ExecutionPackageError, MAX_PACKAGES, MAX_WHEEL_BYTES,
                     StoredPackage, WheelInspection, unique_object, validate_imported_time)

MAX_CACHE_MANIFEST_BYTES = 512 * 1024


def identifier(value: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
        return value
    except (ValueError, TypeError, AttributeError):
        raise ExecutionPackageError("invalid_request") from None


def safe_path(root: Path, path: Path) -> None:
    """Reject links at every existing component and remain below the AppPaths root."""
    relative = path.relative_to(root)
    current = root
    for part in (None, *relative.parts):
        if part is not None:
            current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("cache link")
    if not path.resolve(strict=False).is_relative_to(root.resolve(strict=False)):
        raise ValueError("cache escapes root")


class ExecutionPackageStore:
    def __init__(self, paths: AppPaths):
        self._home = paths.home
        self._root = paths.execution_plugin_packages_dir
        self._lock = RLock()
        if not self._root.is_relative_to(self._home):
            raise ValueError("invalid AppPaths package boundary")

    def _folder(self, package_id):
        return self._root / identifier(package_id)

    def _read(self, folder: Path) -> tuple[StoredPackage, bytes]:
        safe_path(self._home, folder)
        if not folder.is_dir():
            raise ValueError("missing cache directory")
        manifest = folder / "manifest.json"
        safe_path(self._home, manifest)
        if not manifest.is_file():
            raise ValueError("cache manifest is not a regular file")
        with manifest.open("rb") as stream:
            data = stream.read(MAX_CACHE_MANIFEST_BYTES + 1)
        if len(data) > MAX_CACHE_MANIFEST_BYTES:
            raise ValueError("oversized cache manifest")
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
        if type(raw) is not dict or type(raw.get("schemaVersion")) is not int:
            raise ValueError("invalid manifest")
        stored = StoredPackage.model_validate(raw)
        if identifier(stored.id) != folder.name:
            raise ValueError("cache identity mismatch")
        validate_imported_time(stored.importedAt)
        wheel = folder / stored.inspection.fileName
        safe_path(self._home, wheel)
        if not wheel.is_file():
            raise ValueError("cached wheel is not a regular file")
        if set(item.name for item in folder.iterdir()) != {"manifest.json", wheel.name}:
            raise ValueError("unknown cached file")
        with wheel.open("rb") as stream:
            wheel_data = stream.read(MAX_WHEEL_BYTES + 1)
        inspected = inspect_wheel(wheel_data, wheel.name, validate_environment=False,
                                 owners={}, allow_retired_api=True)
        if inspected != stored.inspection:
            raise ValueError("cached wheel changed")
        return stored, wheel_data

    def _list(self):
        safe_path(self._home, self._root)
        if not self._root.exists():
            return []
        entries = list(self._root.iterdir())
        if len(entries) > MAX_PACKAGES:
            raise ExecutionPackageError("package_too_large")
        result = []
        hashes = set()
        for folder in sorted(entries):
            if folder.name.startswith((".incoming-", ".removing-")):
                identifier(folder.name.split("-", 1)[1])
                safe_path(self._home, folder)
                if not folder.is_dir():
                    raise ValueError("inactive cache entry is not a directory")
                inactive = list(folder.iterdir())
                if len(inactive) > 4:
                    raise ValueError("inactive cache directory exceeds bound")
                for item in inactive:
                    safe_path(self._home, item)
                    if not item.is_file() or item.stat().st_size > MAX_WHEEL_BYTES:
                        raise ValueError("invalid inactive cache member")
                # Read-only recognition of this transaction's private staging;
                # never expose, recover or recursively delete orphaned content.
                continue
            identifier(folder.name)
            stored, _ = self._read(folder)
            if stored.inspection.sha256 in hashes:
                raise ValueError("duplicate cached package")
            hashes.add(stored.inspection.sha256)
            result.append(stored)
        return sorted(result, key=lambda stored: (stored.importedAt, stored.id))

    def list(self) -> list[StoredPackage]:
        with self._lock:
            try:
                return self._list()
            except ExecutionPackageError as error:
                if error.code == "package_too_large":
                    raise
                raise ExecutionPackageError("packages_store_unavailable") from None
            except Exception:
                raise ExecutionPackageError("packages_store_unavailable") from None

    def get(self, package_id: str) -> tuple[StoredPackage, bytes]:
        folder = self._folder(package_id)
        with self._lock:
            try:
                safe_path(self._home, folder)
                if not folder.exists():
                    raise ExecutionPackageError("package_not_found")
                return self._read(folder)
            except ExecutionPackageError as error:
                if error.code == "package_not_found":
                    raise
                raise ExecutionPackageError("packages_store_unavailable") from None
            except Exception:
                raise ExecutionPackageError("packages_store_unavailable") from None

    def save(self, inspection: WheelInspection, data: bytes) -> StoredPackage:
        with self._lock:
            stage = None
            try:
                entries = self._list()
                existing = next((item for item in entries if item.inspection.sha256 == inspection.sha256), None)
                if existing is not None:
                    return existing
                if len(entries) >= MAX_PACKAGES or (self._root.exists() and len(list(self._root.iterdir())) >= MAX_PACKAGES):
                    raise ExecutionPackageError("package_too_large")
                package_id = str(uuid4())
                stored = StoredPackage(schemaVersion=1, id=package_id,
                    importedAt=datetime.now(UTC).isoformat(), inspection=inspection)
                payload = json.dumps(stored.model_dump(), ensure_ascii=False, separators=(",", ":")).encode()
                if len(payload) > MAX_CACHE_MANIFEST_BYTES:
                    raise ValueError("cache manifest too large")
                safe_path(self._home, self._root)
                self._root.mkdir(parents=True, mode=0o700, exist_ok=True)
                stage = self._root / (".incoming-" + package_id)
                safe_path(self._home, stage)
                stage.mkdir(mode=0o700)
                atomic_write(stage / inspection.fileName, data)
                atomic_write(stage / "manifest.json", payload)
                destination = self._folder(package_id)
                safe_path(self._home, destination)
                os.replace(stage, destination)
                stage = None
                if os.name != "nt":
                    descriptor = os.open(self._root, os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                return stored
            except ExecutionPackageError as error:
                if error.code == "package_too_large":
                    raise
                raise ExecutionPackageError("packages_store_unavailable") from None
            except Exception:
                raise ExecutionPackageError("packages_store_unavailable") from None
            finally:
                if stage is not None:
                    # Only known files in this newly owned staging directory; never recurse.
                    try:
                        safe_path(self._home, stage)
                        (stage / inspection.fileName).unlink(missing_ok=True)
                        (stage / "manifest.json").unlink(missing_ok=True)
                        stage.rmdir()
                    except OSError:
                        pass

    def delete(self, package_id: str) -> None:
        folder = self._folder(package_id)
        with self._lock:
            try:
                stored, _ = self.get(package_id)
                safe_path(self._home, folder)
                tombstone = self._root / (".removing-" + package_id)
                safe_path(self._home, tombstone)
                if tombstone.exists():
                    raise ValueError("existing removal transaction")
                os.replace(folder, tombstone)
                # Both files have just passed identity, content and boundary validation.
                safe_path(self._home, tombstone)
                (tombstone / stored.inspection.fileName).unlink()
                (tombstone / "manifest.json").unlink()
                tombstone.rmdir()
            except ExecutionPackageError:
                raise
            except Exception:
                raise ExecutionPackageError("packages_store_unavailable") from None
