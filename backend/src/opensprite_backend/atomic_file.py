"""Small cross-platform primitive for durable atomic local-file replacement."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile


def atomic_write(path: Path, payload: bytes) -> None:
    """Replace one local file only after its complete payload is synced."""

    parent = path.parent
    temporary_path: Path | None = None
    file_descriptor: int | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            parent.chmod(0o700)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "wb") as stream:
            file_descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        if os.name != "nt":
            path.chmod(0o600)
            directory_descriptor = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if file_descriptor is not None:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
