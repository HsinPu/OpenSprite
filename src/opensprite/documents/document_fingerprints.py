"""Fingerprint helpers for document-backed workspace files."""

from __future__ import annotations

import hashlib
from pathlib import Path


def fingerprint_text_directory(root: Path | None) -> str:
    """Return a stable content fingerprint for one directory tree."""
    directory = Path(root).expanduser().resolve(strict=False) if root is not None else None
    if directory is None or not directory.is_dir():
        return ""

    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
