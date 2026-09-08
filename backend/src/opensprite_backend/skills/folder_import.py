"""Bounded, portable Skill package validation; never executes package content."""
from __future__ import annotations

from dataclasses import dataclass, field
import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
import unicodedata

from opensprite_backend.workspaces import WorkspaceRootPolicy
from .format import parse
from .models import SkillError

MAX_FILES = 200
MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_DEPTH = 8
FORBIDDEN_DIRECTORIES = frozenset({".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"})


def disk_path(path: Path) -> Path:
    """Use Windows extended paths only for internal, already-derived disk paths."""
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


class FolderImportError(SkillError):
    def __init__(self, code: str, path: str | None = None):
        # Only a validated package-relative path may be returned to the browser.
        self.path = path
        super().__init__(code)


@dataclass(frozen=True)
class PackageFile:
    path: str
    data: bytes = field(repr=False)


@dataclass(frozen=True)
class SkillPackage:
    directory_name: str
    name: str
    description: str
    files: tuple[PackageFile, ...] = field(repr=False)
    manifest_hash: str


def safe_segment(value: str) -> str:
    try:
        return WorkspaceRootPolicy.directory_name(value)
    except ValueError:
        raise FolderImportError("unsafe_path") from None


def validate_paths(paths: list[str]) -> tuple[str, ...]:
    if not 1 <= len(paths) <= MAX_FILES:
        raise FolderImportError("file_count_exceeded")
    normalized: list[str] = []
    nodes: dict[str, tuple[str, bool]] = {}
    for value in paths:
        if not isinstance(value, str) or len(value) > 720:
            raise FolderImportError("unsafe_path")
        parts = value.split("/")
        if len(parts) > MAX_DEPTH:
            raise FolderImportError("directory_depth_exceeded")
        canonical = [safe_segment(part) for part in parts]
        relative = "/".join(canonical)
        # Preserve spelling rather than silently rename decomposed Unicode.
        if relative != value:
            raise FolderImportError("noncanonical_path")
        if any(part.casefold() in FORBIDDEN_DIRECTORIES for part in canonical):
            raise FolderImportError("excluded_directory", relative)
        if len(parts) > 1 and parts[-1].casefold() == "skill.md":
            raise FolderImportError("nested_skill", relative)
        if parts[-1].casefold() == "skill.md" and relative != "SKILL.md":
            raise FolderImportError("invalid_entrypoint", relative)
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = unicodedata.normalize("NFC", prefix).casefold()
            is_file = index == len(parts)
            previous = nodes.get(key)
            if previous is not None and (previous[0] != prefix or previous[1] or is_file):
                raise FolderImportError("duplicate_path", relative)
            nodes[key] = (prefix, is_file)
        normalized.append(relative)
    if "SKILL.md" not in normalized:
        raise FolderImportError("missing_entrypoint")
    return tuple(normalized)


def validate_package(directory_name: str, files: tuple[PackageFile, ...]) -> SkillPackage:
    directory = safe_segment(directory_name)
    if directory != directory_name or directory.casefold() in FORBIDDEN_DIRECTORIES:
        raise FolderImportError("invalid_directory_name")
    paths = validate_paths([item.path for item in files])
    total = 0
    digest = hashlib.sha256()
    for item in sorted(files, key=lambda item: item.path):
        if not isinstance(item.data, bytes):
            raise FolderImportError("invalid_request")
        limit = 65536 if item.path == "SKILL.md" else MAX_FILE_BYTES
        if len(item.data) > limit:
            raise FolderImportError("content_too_large", item.path)
        total += len(item.data)
        if total > MAX_TOTAL_BYTES:
            raise FolderImportError("package_too_large")
        digest.update(item.path.encode("utf-8") + b"\0" + hashlib.sha256(item.data).digest())
    entry = files[paths.index("SKILL.md")]
    try:
        name, description, _, _ = parse(entry.data.decode("utf-8"))
    except (UnicodeError, SkillError):
        raise FolderImportError("invalid_format", "SKILL.md") from None
    return SkillPackage(directory, name, description, files, digest.hexdigest())


def recover_package(service, tx: dict) -> None:
    """Roll forward only the package named in a durable, validated journal."""
    from opensprite_backend.atomic_file import atomic_write
    from opensprite_backend.workspaces.relocation import ensure_plain_directory, require_plain_directory
    from .models import SkillRecord, LegacySkillRecord

    if set(tx) != {"version", "catalog", "record", "files"} or tx["version"] != 2:
        raise SkillError("store_unavailable")
    catalog = service._validate(tx["catalog"])
    item = (LegacySkillRecord if catalog.version < 3 else SkillRecord).model_validate(tx["record"])
    if (catalog.version == 1 and item.enabled) or item.confirmedHash is not None or service._find(catalog, item.id) != item:
        raise SkillError("store_unavailable")
    if not isinstance(tx["files"], list) or not 1 <= len(tx["files"]) <= MAX_FILES:
        raise SkillError("store_unavailable")
    files = []
    for value in tx["files"]:
        if type(value) is not dict or set(value) != {"path", "data"}:
            raise SkillError("store_unavailable")
        files.append(PackageFile(value["path"], base64.b64decode(value["data"], validate=True)))
    package = validate_package(item.directoryName, tuple(files))
    if package.name != item.name or package.description != item.description:
        raise SkillError("store_unavailable")
    target = disk_path(service._path(item).parent)
    stage = target.parent / f".skill-import-{item.id}"
    service._safe_file(target / "SKILL.md", missing=True)
    service._safe_file(stage / "SKILL.md", missing=True)
    if target.exists():
        # Rename succeeded before catalog replacement. Never overwrite the target.
        require_plain_directory(target)
        verify_tree(service, target, package)
        if stage.exists():
            raise SkillError("store_unavailable")
    else:
        try:
            ensure_plain_directory(stage)
            for entry in package.files:
                path = stage.joinpath(*entry.path.split("/"))
                service._safe_file(path, missing=True)
                ensure_plain_directory(path.parent)
                atomic_write(path, entry.data)
            verify_tree(service, stage, package)
            stage.rename(target)
        except (OSError, SkillError):
            if not target.exists():
                # Nothing was published: retain diagnostics outside the scan root
                # and remove this failed operation from automatic recovery.
                archive = disk_path(service.paths.skills_archive_dir / f"failed-import-{item.id}-{uuid4()}")
                ensure_plain_directory(archive.parent)
                if archive.exists():
                    raise SkillError("store_unavailable") from None
                ensure_plain_directory(archive)
                if stage.exists():
                    require_plain_directory(stage)
                    stage.rename(archive / "payload")
                service.paths.skills_transaction_file.rename(archive / "transaction.json")
            raise SkillError("store_unavailable") from None
    atomic_write(service.paths.skills_settings_file, catalog.model_dump_json().encode())
    service.paths.skills_transaction_file.unlink()


def verify_tree(service, root: Path, package: SkillPackage) -> None:
    from opensprite_backend.workspaces.relocation import require_plain_directory
    expected = {item.path: item for item in package.files}
    observed = set()
    for path in root.rglob("*"):
        service._safe_file(path, missing=True)
        if path.is_dir():
            require_plain_directory(path)
            continue
        relative = path.relative_to(root).as_posix()
        entry = expected.get(relative)
        if entry is None or not path.is_file() or path.stat().st_size != len(entry.data):
            raise SkillError("store_unavailable")
        with path.open("rb") as stream:
            if stream.read(len(entry.data) + 1) != entry.data:
                raise SkillError("store_unavailable")
        observed.add(relative)
    if observed != expected.keys():
        raise SkillError("store_unavailable")


def journal_bytes(catalog, item, package: SkillPackage) -> bytes:
    payload = json.dumps({"version": 2, "catalog": catalog.model_dump(), "record": item.model_dump(),
                          "files": [{"path": entry.path, "data": base64.b64encode(entry.data).decode("ascii")} for entry in package.files]}).encode()
    if len(payload) > 16 * 1024 * 1024:
        raise SkillError("store_unavailable")
    return payload
