"""Restartable copy-and-verify relocation; source directories are never removed."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from uuid import uuid4

from opensprite_backend.atomic_file import atomic_write


class WorkspaceRelocationError(Exception):
    """Path-free failure suitable for runtime reporting."""


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkspaceRelocationError
        result[key] = value
    return result


def require_plain_directory(path: Path) -> None:
    for node in (path, *path.parents):
        info = node.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise WorkspaceRelocationError
    if not path.is_dir():
        raise WorkspaceRelocationError


def ensure_plain_directory(path: Path) -> None:
    for node in (path, *path.parents):
        if node.exists() or node.is_symlink():
            require_plain_directory(node)
    path.mkdir(parents=True, exist_ok=True)
    require_plain_directory(path)


def tree_manifest(root: Path) -> str:
    require_plain_directory(root)
    entries: list[tuple[str, str]] = []
    for directory, folders, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        require_plain_directory(parent)
        for name in sorted(folders + files):
            path = parent / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise WorkspaceRelocationError
            if stat.S_ISDIR(info.st_mode):
                digest = "directory"
            elif stat.S_ISREG(info.st_mode):
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                after = path.stat()
                if (info.st_size, info.st_mtime_ns, info.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                    raise WorkspaceRelocationError
            else:
                raise WorkspaceRelocationError
            entries.append((path.relative_to(root).as_posix(), digest))
    return hashlib.sha256(json.dumps(sorted(entries), ensure_ascii=False).encode()).hexdigest()


class WorkspaceRelocator:
    def __init__(self, source: Path, destination: Path, journal: Path) -> None:
        self.source = source
        self.destination = destination
        self.journal = journal

    def relocate(self, names: tuple[str, ...]) -> None:
        try:
            self._relocate(names)
        except (OSError, ValueError, RuntimeError, WorkspaceRelocationError):
            raise WorkspaceRelocationError from None

    def _relocate(self, names: tuple[str, ...]) -> None:
        completed: dict[str, str] = {}
        if self.journal.exists():
            require_plain_directory(self.journal.parent)
            if self.journal.is_symlink():
                raise WorkspaceRelocationError
            with self.journal.open("rb") as stream:
                content = stream.read(32769)
            if len(content) > 32768:
                raise WorkspaceRelocationError
            raw = json.loads(content, object_pairs_hook=_unique_fields)
            if not isinstance(raw, dict) or set(raw) != {"version", "entries"} or type(raw["version"]) is not int or raw["version"] != 1 or not isinstance(raw["entries"], dict):
                raise WorkspaceRelocationError
            completed = raw["entries"]
            if any(type(k) is not str or type(v) is not str or len(v) != 64 for k, v in completed.items()):
                raise WorkspaceRelocationError
        ensure_plain_directory(self.destination)
        for name in names:
            if Path(name).name != name or name in {"", ".", ".."}:
                raise WorkspaceRelocationError
            source, target = self.source / name, self.destination / name
            if not source.exists():
                # Preserve unavailable old roots rather than inventing empty data.
                if source.is_symlink() or target.exists():
                    raise WorkspaceRelocationError
                continue
            before = tree_manifest(source)
            if target.exists():
                if completed.get(name) != before or tree_manifest(target) != before:
                    raise WorkspaceRelocationError
                continue
            # UUID staging directories are retained on failure; never erase user data.
            staging = self.destination.parent / "cache" / "workspace-relocation" / str(uuid4())
            ensure_plain_directory(staging.parent)
            shutil.copytree(source, staging, symlinks=True)
            if tree_manifest(staging) != before or tree_manifest(source) != before:
                raise WorkspaceRelocationError
            completed[name] = before
            atomic_write(self.journal, json.dumps({"version": 1, "entries": completed}, separators=(",", ":")).encode())
            require_plain_directory(self.destination)
            if target.exists():
                raise WorkspaceRelocationError
            staging.rename(target)
