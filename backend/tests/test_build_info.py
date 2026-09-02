from __future__ import annotations

import json
from pathlib import Path

import pytest

from opensprite_backend.build_info import load_app_info, product_version


def test_development_info_uses_package_version_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    info = load_app_info(path)

    assert info.version == product_version() == "0.2.4"
    assert info.revision == "development"
    assert info.buildType == "development"
    assert info.dirty is True
    assert info.installedAt is None
    assert not path.exists()


def test_installed_info_requires_matching_package_version(tmp_path: Path) -> None:
    path = tmp_path / "build-info.json"
    path.write_text(json.dumps({
        "version": "0.2.4",
        "revision": "84142959",
        "dirty": False,
        "installedAt": "2026-08-31T01:02:03Z",
    }), encoding="utf-8")

    info = load_app_info(path)

    assert info.model_dump(mode="json") == {
        "version": "0.2.4",
        "revision": "84142959",
        "buildType": "installed",
        "dirty": False,
        "installedAt": "2026-08-31T01:02:03Z",
    }


@pytest.mark.parametrize("payload", [
    "not-json",
    '{"version":"0.2.0","revision":"84142959","dirty":false}',
    '{"version":"9.9.9","revision":"84142959","dirty":false,"installedAt":"2026-08-31T01:02:03Z"}',
    '{"version":"0.2.0","revision":"invalid!","dirty":false,"installedAt":"2026-08-31T01:02:03Z"}',
    '{"version":"0.2.0","version":"0.2.0","revision":"84142959","dirty":false,"installedAt":"2026-08-31T01:02:03Z"}',
])
def test_invalid_build_info_fails_closed(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "build-info.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(RuntimeError, match="build metadata"):
        load_app_info(path)
