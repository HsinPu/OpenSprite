"""Windows IFileOpenDialog adapter without a shell command."""

from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
from uuid import UUID

from .service import LocalPathPickerError, PathKind


_COINIT_APARTMENTTHREADED = 0x2
_CLSCTX_INPROC_SERVER = 0x1
_FOS_PICKFOLDERS = 0x20
_FOS_FORCEFILESYSTEM = 0x40
_FOS_PATHMUSTEXIST = 0x800
_FOS_FILEMUSTEXIST = 0x1000
_SIGDN_FILESYSPATH = 0x80058000
_CANCELLED = 0x800704C7


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, value: str) -> "_Guid":
        raw = UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


def _method(pointer: ctypes.c_void_p, index: int, restype, *argtypes):
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(vtable[index])


def _check(result: int) -> None:
    if result < 0:
        raise OSError(result)


class WindowsPathPicker:
    async def pick(self, kind: PathKind) -> str | None:
        return await asyncio.to_thread(self._pick_sync, kind)

    @staticmethod
    def _pick_sync(kind: PathKind) -> str | None:
        ole32 = ctypes.OleDLL("ole32")
        initialized = ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
        if initialized not in (0, 1):
            raise LocalPathPickerError("picker_unavailable")
        dialog = ctypes.c_void_p()
        item = ctypes.c_void_p()
        display_name = ctypes.c_wchar_p()
        try:
            clsid = _Guid.parse("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")
            iid = _Guid.parse("D57C7288-D4AD-4768-BE02-9D969532D960")
            _check(ole32.CoCreateInstance(
                ctypes.byref(clsid),
                None,
                _CLSCTX_INPROC_SERVER,
                ctypes.byref(iid),
                ctypes.byref(dialog),
            ))
            options = wintypes.DWORD()
            _check(_method(dialog, 10, ctypes.c_long, ctypes.POINTER(wintypes.DWORD))(
                dialog, ctypes.byref(options)
            ))
            flags = options.value | _FOS_FORCEFILESYSTEM | _FOS_PATHMUSTEXIST
            flags |= _FOS_PICKFOLDERS if kind == "directory" else _FOS_FILEMUSTEXIST
            _check(_method(dialog, 9, ctypes.c_long, wintypes.DWORD)(dialog, flags))
            title = "Select working directory" if kind == "directory" else "Select executable"
            _check(_method(dialog, 17, ctypes.c_long, wintypes.LPCWSTR)(dialog, title))
            shown = _method(dialog, 3, ctypes.c_long, wintypes.HWND)(dialog, None)
            if shown & 0xFFFFFFFF == _CANCELLED:
                return None
            _check(shown)
            _check(_method(dialog, 20, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(
                dialog, ctypes.byref(item)
            ))
            _check(_method(item, 5, ctypes.c_long, wintypes.DWORD, ctypes.POINTER(ctypes.c_wchar_p))(
                item, _SIGDN_FILESYSPATH, ctypes.byref(display_name)
            ))
            return display_name.value
        finally:
            if display_name:
                ole32.CoTaskMemFree(display_name)
            if item:
                _method(item, 2, wintypes.ULONG)(item)
            if dialog:
                _method(dialog, 2, wintypes.ULONG)(dialog)
            ole32.CoUninitialize()
