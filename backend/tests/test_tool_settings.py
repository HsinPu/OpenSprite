"""Tests for the production tool catalog and persisted availability settings."""

from __future__ import annotations

from asyncio import run
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.models import ToolSettings
from opensprite_backend.runtime import create_system_app, create_system_runtime
from opensprite_backend.tool_settings import (
    JsonToolSettingsStore,
    ToolNotFoundError,
    ToolSettingsService,
    ToolSettingsStoreError,
)
from opensprite_backend.tools import create_production_tool_registry


def settings(
    enabled: bool = True,
    enabled_tools: list[str] | None = None,
) -> ToolSettings:
    return ToolSettings(
        enabled=enabled,
        enabledTools=["calculator"] if enabled_tools is None else enabled_tools,
    )


def service(path: Path) -> ToolSettingsService:
    return ToolSettingsService(
        JsonToolSettingsStore(path),
        create_production_tool_registry(),
    )


def test_store_round_trip_and_lazy_default_read(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonToolSettingsStore(paths.tool_settings_file)

    assert store.get() == settings()
    assert not paths.home.exists()
    saved = settings(False, [])
    store.set(saved)

    assert store.get() == saved
    assert json.loads(paths.tool_settings_file.read_text(encoding="utf-8")) == {
        "version": 1,
        "enabled": False,
        "enabledTools": [],
    }
    assert sorted(
        path.relative_to(paths.home).as_posix() for path in paths.home.rglob("*")
    ) == ["config", "config/tools.json"]


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":1,"enabled":true,"enabledTools":["calculator"],"extra":true}',
        '{"version":1,"version":1,"enabled":true,"enabledTools":[]}',
        '{"version":2,"enabled":true,"enabledTools":[]}',
        '{"version":1,"enabled":1,"enabledTools":[]}',
        '{"version":1,"enabled":true,"enabledTools":["calculator","calculator"]}',
        '{"version":1,"enabled":true,"enabledTools":["Bad Tool"]}',
    ],
)
def test_store_rejects_malformed_or_noncanonical_json(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "tools.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ToolSettingsStoreError) as raised:
        JsonToolSettingsStore(path).get()

    assert str(raised.value) == "Tool settings are unavailable."


def test_store_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "tools.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(ToolSettingsStoreError):
        JsonToolSettingsStore(path).get()


def test_atomic_failure_cleans_temp_and_preserves_old_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config" / "tools.json"
    store = JsonToolSettingsStore(path)
    store.set(settings())
    before = path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("private replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(ToolSettingsStoreError):
        store.set(settings(False, []))

    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_service_catalog_settings_and_snapshot(tmp_path: Path) -> None:
    operations = service(tmp_path / "tools.json")

    catalog = run(operations.list_tools())
    assert catalog.model_dump(mode="json") == {
        "items": [
            {
                "id": "calculator",
                "source": "builtin",
                "effect": "read_only",
                "available": True,
            }
        ]
    }
    assert run(operations.snapshot()).enabled_names == frozenset({"calculator"})
    assert run(operations.put(settings(False))) == settings(False)
    assert run(operations.snapshot()).enabled_names == frozenset()

    with pytest.raises(ToolNotFoundError):
        run(operations.put(settings(True, ["missing_tool"])))


def test_api_round_trip_validation_and_unknown_tool(tmp_path: Path) -> None:
    operations = service(tmp_path / "tools.json")
    with TestClient(create_app(tool_settings=operations)) as client:
        catalog = client.get("/api/tools")
        initial = client.get("/api/settings/tools")
        saved = client.put(
            "/api/settings/tools",
            json={"enabled": False, "enabledTools": ["calculator"]},
        )
        malformed = client.put(
            "/api/settings/tools",
            json={"enabled": "yes", "enabledTools": []},
        )
        unknown = client.put(
            "/api/settings/tools",
            json={"enabled": True, "enabledTools": ["missing_tool"]},
        )

    assert catalog.status_code == 200
    assert catalog.json()["items"][0]["id"] == "calculator"
    assert initial.json() == {"enabled": True, "enabledTools": ["calculator"]}
    assert saved.json() == {"enabled": False, "enabledTools": ["calculator"]}
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_request"
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "tool_not_found"


def test_same_origin_protection_applies_to_tool_settings_put(tmp_path: Path) -> None:
    app = create_app(
        tool_settings=service(tmp_path / "tools.json"),
        enforce_local_security=True,
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.put(
            "/api/settings/tools",
            headers={"Origin": "http://evil.example"},
            json={"enabled": False, "enabledTools": []},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_corrupt_store_maps_to_sanitized_503(tmp_path: Path) -> None:
    path = tmp_path / "tools.json"
    path.write_text("not-json", encoding="utf-8")

    with TestClient(create_app(tool_settings=service(path))) as client:
        response = client.get("/api/settings/tools")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "settings_store_unavailable",
            "message": "Tool settings are unavailable.",
            "retryable": True,
        }
    }


def test_runtime_composes_tool_settings_without_creating_config(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    runtime = create_system_runtime(app_paths=paths)

    assert runtime.tool_settings.__class__.__name__ == "ToolSettingsService"
    assert not paths.home.exists()
    run(runtime.aclose())

    app = create_system_app(app_paths=paths)
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/settings/tools")
        assert response.status_code == 200
        assert response.json() == {
            "enabled": True,
            "enabledTools": ["calculator"],
        }
    assert paths.backend_logs_dir.is_dir()
    assert not paths.config_dir.exists()
