"""Resolve one product version plus reproducible installed-build metadata."""

from __future__ import annotations

from importlib.metadata import version as package_version
import json
from pathlib import Path
from typing import Final

from .models import AppInfo

_PACKAGE_NAME: Final = "opensprite-backend"
_MAX_BUILD_INFO_BYTES: Final = 16 * 1024


def default_build_info_file() -> Path:
    return Path(__file__).resolve().parents[3] / "build-info.json"


def product_version() -> str:
    return package_version(_PACKAGE_NAME)


def load_app_info(path: str | Path | None = None) -> AppInfo:
    build_file = default_build_info_file() if path is None else Path(path)
    version = product_version()
    try:
        data = build_file.read_bytes()
    except FileNotFoundError:
        return AppInfo(
            version=version,
            revision="development",
            buildType="development",
            dirty=True,
            installedAt=None,
        )
    if len(data) > _MAX_BUILD_INFO_BYTES:
        raise RuntimeError("OpenSprite build metadata is invalid.")
    try:
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
        if type(raw) is not dict or set(raw) != {
            "version",
            "revision",
            "dirty",
            "installedAt",
        }:
            raise ValueError
        info = AppInfo.model_validate({**raw, "buildType": "installed"})
    except Exception as error:
        raise RuntimeError("OpenSprite build metadata is invalid.") from error
    if info.version != version or info.installedAt is None:
        raise RuntimeError("OpenSprite build metadata does not match the installed package.")
    return info


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate build metadata key")
        result[key] = value
    return result
