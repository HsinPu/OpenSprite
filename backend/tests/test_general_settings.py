"""Tests for strict persisted language and time-zone settings."""

from __future__ import annotations

from asyncio import run
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.general_settings import (
    GeneralSettingsService,
    GeneralSettingsStoreError,
    JsonGeneralSettingsStore,
)
from opensprite_backend.models import GeneralSettings
from opensprite_backend.runtime import create_system_app, create_system_runtime


def settings(locale: str = "zh-TW", time_zone: str = "system") -> GeneralSettings:
    return GeneralSettings(locale=locale, timeZone=time_zone)  # type: ignore[arg-type]


def test_store_round_trip_and_lazy_default_read(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonGeneralSettingsStore(paths.general_settings_file)

    assert store.get() == settings()
    assert not paths.home.exists()
    saved = settings("ja", "Asia/Taipei")
    store.set(saved)

    assert store.get() == saved
    assert json.loads(paths.general_settings_file.read_text(encoding="utf-8")) == {
        "version": 1,
        "locale": "ja",
        "timeZone": "Asia/Taipei",
    }
    assert sorted(path.relative_to(paths.home).as_posix() for path in paths.home.rglob("*")) == [
        "config",
        "config/general.json",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":1,"locale":"zh-TW","timeZone":"system","extra":true}',
        '{"version":1,"version":1,"locale":"zh-TW","timeZone":"system"}',
        '{"version":2,"locale":"zh-TW","timeZone":"system"}',
        '{"version":1,"locale":"other","timeZone":"system"}',
        '{"version":1,"locale":"en","timeZone":"Asia/Tokyo"}',
    ],
)
def test_store_rejects_malformed_or_noncanonical_json(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "general.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(GeneralSettingsStoreError) as raised:
        JsonGeneralSettingsStore(path).get()

    assert str(raised.value) == "General settings are unavailable."
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_store_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "general.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(GeneralSettingsStoreError):
        JsonGeneralSettingsStore(path).get()


def test_atomic_failure_cleans_temp_and_preserves_old_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config" / "general.json"
    store = JsonGeneralSettingsStore(path)
    store.set(settings())
    before = path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("private replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(GeneralSettingsStoreError):
        store.set(settings("en", "UTC"))

    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_service_and_api_round_trip_and_validation(tmp_path: Path) -> None:
    service = GeneralSettingsService(
        JsonGeneralSettingsStore(tmp_path / "general.json")
    )
    assert run(service.get()) == settings()
    assert run(service.put(settings("en", "UTC"))) == settings("en", "UTC")

    with TestClient(create_app(general_settings=service)) as client:
        initial = client.get("/api/settings/general")
        saved = client.put(
            "/api/settings/general",
            json={"locale": "ja", "timeZone": "Asia/Taipei"},
        )
        invalid = client.put(
            "/api/settings/general",
            json={"locale": "other", "timeZone": "UTC"},
        )

    assert initial.json() == {"locale": "en", "timeZone": "UTC"}
    assert saved.status_code == 200
    assert saved.json() == {"locale": "ja", "timeZone": "Asia/Taipei"}
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_request"


def test_same_origin_protection_applies_to_general_settings_put(tmp_path: Path) -> None:
    service = GeneralSettingsService(
        JsonGeneralSettingsStore(tmp_path / "general.json")
    )
    app = create_app(general_settings=service, enforce_local_security=True)
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.put(
            "/api/settings/general",
            headers={"Origin": "http://evil.example"},
            json={"locale": "en", "timeZone": "UTC"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_corrupt_store_maps_to_sanitized_503(tmp_path: Path) -> None:
    path = tmp_path / "general.json"
    path.write_text("not-json", encoding="utf-8")
    service = GeneralSettingsService(JsonGeneralSettingsStore(path))

    with TestClient(create_app(general_settings=service)) as client:
        response = client.get("/api/settings/general")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "settings_store_unavailable",
            "message": "General settings are unavailable.",
            "retryable": True,
        }
    }


def test_runtime_composes_general_settings_without_creating_data(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    runtime = create_system_runtime(app_paths=paths)

    assert runtime.general_settings.__class__.__name__ == "GeneralSettingsService"
    assert not paths.home.exists()
    run(runtime.aclose())

    app = create_system_app(app_paths=paths)
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/settings/general")
        assert response.status_code == 200
        assert response.json() == {"locale": "zh-TW", "timeZone": "system"}
    assert not paths.home.exists()
