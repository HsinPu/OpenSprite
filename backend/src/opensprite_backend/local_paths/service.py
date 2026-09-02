"""Safe application boundary for native path-picker dialogs."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Literal, Protocol


PathKind = Literal["executable", "directory"]


class LocalPathPickerError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class NativePathPicker(Protocol):
    async def pick(self, kind: PathKind) -> str | None: ...


class LocalPathPickerOperations(Protocol):
    async def pick(self, kind: PathKind) -> str | None: ...


class UnavailableLocalPathPicker:
    async def pick(self, kind: PathKind) -> str | None:
        del kind
        raise LocalPathPickerError("picker_unavailable")


class LocalPathPickerService:
    def __init__(self, native: NativePathPicker) -> None:
        self._native = native
        self._gate = asyncio.Lock()

    async def pick(self, kind: PathKind) -> str | None:
        if self._gate.locked():
            raise LocalPathPickerError("picker_busy")
        async with self._gate:
            try:
                selected = await self._native.pick(kind)
            except LocalPathPickerError:
                raise
            except Exception:
                raise LocalPathPickerError("picker_unavailable") from None
        if selected is None:
            return None
        return _validated_path(selected, kind)


def _validated_path(value: str, kind: PathKind) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 32_768
        or any(character in value for character in ("\x00", "\r", "\n"))
    ):
        raise LocalPathPickerError("invalid_selection")
    path = Path(value)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise LocalPathPickerError("invalid_selection") from None
    if not path.is_absolute() or path.is_symlink():
        raise LocalPathPickerError("invalid_selection")
    if kind == "executable" and not resolved.is_file():
        raise LocalPathPickerError("invalid_selection")
    if kind == "directory" and not resolved.is_dir():
        raise LocalPathPickerError("invalid_selection")
    return str(resolved)


def create_local_path_picker() -> LocalPathPickerOperations:
    if sys.platform == "win32":
        from .windows import WindowsPathPicker

        return LocalPathPickerService(WindowsPathPicker())
    if sys.platform.startswith("linux"):
        from .linux import LinuxPortalPathPicker

        return LocalPathPickerService(LinuxPortalPathPicker())
    return UnavailableLocalPathPicker()
