"""Persistence and HTTP boundaries for execution plugin selection."""

import asyncio
from asyncio import run
from dataclasses import replace
import json
import os
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.agent.plugin_catalog import ExecutionPluginError, PluginDescriptor
from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.execution_settings import ExecutionSettingsError, ExecutionSettingsService


class Catalog:
    def __init__(self) -> None:
        self.items = (
            PluginDescriptor("standard", "loop", "Standard Loop", "Default loop.", "1.0.0", 1),
            PluginDescriptor("standard", "policy", "Standard", "Default recovery.", "1.0.0", 1),
            PluginDescriptor("no_recovery", "policy", "No recovery", "No automatic recovery.", "1.0.0", 1),
        )
        self.validated: list[tuple[str, str]] = []

    def descriptors(self) -> tuple[PluginDescriptor, ...]:
        return self.items

    def validate_selection(self, loop_id: str, policy_id: str) -> None:
        self.validated.append((loop_id, policy_id))
        for kind, identifier in (("loop", loop_id), ("policy", policy_id)):
            item = next((item for item in self.items if item.kind == kind and item.id == identifier), None)
            if item is None:
                raise ExecutionPluginError("invalid_request")
            if item.status != "available":
                raise ExecutionPluginError("plugin_unavailable")


def test_default_read_is_lazy_and_does_not_load_factories(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    catalog = Catalog()
    service = ExecutionSettingsService(paths, catalog)
    result = run(service.get())
    assert result.selection.model_dump(by_alias=True) == {"loopId": "standard", "policyId": "standard"}
    assert catalog.validated == []
    assert not paths.home.exists()
    assert service.selection() == ("standard", "standard")
    assert catalog.validated == [("standard", "standard")]
    assert not paths.home.exists()


def test_plugin_validation_in_put_does_not_block_other_event_loop_work(tmp_path: Path) -> None:
    from test_execution_plugin_catalog import InstalledPoint, LOOPS

    from opensprite_backend.agent.plugin_catalog import ExecutionPluginCatalog
    from opensprite_backend.agent.standard_driver import StandardDriverFactory

    entered, release = Event(), Event()

    def provider():
        entered.set()
        if not release.wait(1):
            raise TimeoutError("The event loop could not release the loading factory.")
        return StandardDriverFactory()

    point = InstalledPoint("waiting", LOOPS, provider)
    paths = build_app_paths(tmp_path / ".opensprite")
    service = ExecutionSettingsService(paths, ExecutionPluginCatalog((point,)))

    async def scenario():
        async def unrelated_work():
            for _ in range(200):
                if entered.is_set():
                    release.set()
                    return
                await asyncio.sleep(0.001)
            raise AssertionError("Plugin validation did not start.")

        concurrent = asyncio.create_task(unrelated_work())
        try:
            saved = await service.update("waiting", "standard")
            await concurrent
            assert saved.selection.loop_id == "waiting"
        finally:
            release.set()
            concurrent.cancel()
            await asyncio.gather(concurrent, return_exceptions=True)

    run(scenario())
    assert point.loads == 1
    assert service.selection() == ("waiting", "standard")


def test_first_successful_put_persists_only_fixed_selection_schema(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    service = ExecutionSettingsService(paths, Catalog())
    saved = run(service.update("standard", "no_recovery"))
    assert saved.selection.policy_id == "no_recovery"
    assert service.selection() == ("standard", "no_recovery")
    assert json.loads(paths.execution_settings_file.read_text(encoding="utf-8")) == {
        "version": 1, "loopId": "standard", "policyId": "no_recovery",
    }
    assert sorted(path.relative_to(paths.home).as_posix() for path in paths.home.rglob("*")) == ["config", "config/execution.json"]
    if os.name != "nt":
        assert paths.config_dir.stat().st_mode & 0o777 == 0o700
        assert paths.execution_settings_file.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("payload", [
    "not-json", "null", "{}",
    '{"version":true,"loopId":"standard","policyId":"standard"}',
    '{"version":2,"loopId":"standard","policyId":"standard"}',
    '{"version":1,"loopId":"standard","loopId":"standard","policyId":"standard"}',
    '{"version":1,"loopId":"standard","policyId":"standard","extra":true}',
    '{"version":1,"loopId":true,"policyId":"standard"}',
    '{"version":1,"loopId":"../private","policyId":"standard"}',
])
def test_corrupt_store_is_rejected_without_sensitive_exception_context(tmp_path: Path, payload: str) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    paths.config_dir.mkdir(parents=True)
    paths.execution_settings_file.write_text(payload, encoding="utf-8")
    service = ExecutionSettingsService(paths, Catalog())
    with pytest.raises(ExecutionSettingsError) as raised:
        run(service.get())
    assert raised.value.code == "settings_store_unavailable"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_oversized_store_is_rejected(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    paths.config_dir.mkdir(parents=True)
    paths.execution_settings_file.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(ExecutionSettingsError, match="settings_store_unavailable"):
        run(ExecutionSettingsService(paths, Catalog()).get())


def test_get_preserves_missing_selection_so_user_can_replace_it(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    service = ExecutionSettingsService(paths, Catalog())
    run(service.update("standard", "no_recovery"))
    catalog = Catalog()
    catalog.items = catalog.items[:2] + (PluginDescriptor("future", "policy", "Future", "Future API.", "2.0.0", 2, "incompatible"),)
    replacement = ExecutionSettingsService(paths, catalog)
    response = run(replacement.get())
    assert response.selection.policy_id == "no_recovery"
    assert response.plugins[-1].api_version == 2
    assert catalog.validated == []
    with pytest.raises(ExecutionSettingsError, match="invalid_request"):
        replacement.selection()
    assert run(replacement.update("standard", "standard")).selection.policy_id == "standard"


@pytest.mark.parametrize(("loop_id", "policy_id", "code"), [
    ("unknown", "standard", "invalid_request"),
    ("standard", "unknown", "invalid_request"),
    ("no_recovery", "standard", "invalid_request"),
    ("standard", "no_recovery", "plugin_unavailable"),
    (" standard", "standard", "invalid_request"),
])
def test_invalid_or_unavailable_selection_does_not_create_settings(tmp_path: Path, loop_id: str, policy_id: str, code: str) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    catalog = Catalog()
    catalog.items = catalog.items[:2] + (replace(catalog.items[2], status="unavailable"),)
    with pytest.raises(ExecutionSettingsError, match=code):
        run(ExecutionSettingsService(paths, catalog).update(loop_id, policy_id))
    assert not paths.home.exists()


def test_write_failure_preserves_previous_selection_and_cleans_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    service = ExecutionSettingsService(paths, Catalog())
    run(service.update("standard", "standard"))
    before = paths.execution_settings_file.read_bytes()

    def fail_replace(*args: object) -> None:
        raise OSError("private path and credential")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(ExecutionSettingsError) as raised:
        run(service.update("standard", "no_recovery"))
    assert raised.value.code == "settings_store_unavailable"
    assert raised.value.__context__ is None
    assert paths.execution_settings_file.read_bytes() == before
    assert list(paths.config_dir.glob("*.tmp")) == []


def test_broken_catalog_is_not_written(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    catalog = Catalog()
    catalog.items += (catalog.items[0],)
    with pytest.raises(ExecutionSettingsError, match="plugin_unavailable"):
        run(ExecutionSettingsService(paths, catalog).update("standard", "standard"))
    assert not paths.home.exists()


def test_http_round_trip_and_sanitized_errors(tmp_path: Path) -> None:
    catalog = Catalog()
    service = ExecutionSettingsService(build_app_paths(tmp_path / ".opensprite"), catalog)
    with TestClient(create_app(execution_settings=service)) as client:
        initial = client.get("/api/settings/execution")
        assert initial.status_code == 200
        assert initial.json()["selection"] == {"loopId": "standard", "policyId": "standard"}
        saved = client.put("/api/settings/execution", json={"loopId": "standard", "policyId": "no_recovery"})
        assert saved.status_code == 200
        assert saved.json()["selection"]["policyId"] == "no_recovery"
        invalid = client.put("/api/settings/execution", json={"loopId": "unknown", "policyId": "standard"})
        assert invalid.status_code == 400
        assert invalid.json() == {"error": {"code": "invalid_request", "message": "Request validation failed.", "retryable": False}}
        catalog.items = tuple(replace(item, status="unavailable") if item.kind == "policy" and item.id == "no_recovery" else item for item in catalog.items)
        unavailable = client.put("/api/settings/execution", json={"loopId": "standard", "policyId": "no_recovery"})
        assert unavailable.status_code == 503
        assert unavailable.json() == {"error": {"code": "plugin_unavailable", "message": "Execution plugins are unavailable.", "retryable": True}}


@pytest.mark.parametrize("payload", [
    {}, {"loopId": "standard"}, {"loopId": True, "policyId": "standard"},
    {"loop_id": "standard", "policy_id": "standard"},
    {"loopId": "standard", "policyId": "standard", "version": "1.0.0"},
])
def test_http_rejects_noncanonical_request_fields(tmp_path: Path, payload: object) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    with TestClient(create_app(execution_settings=ExecutionSettingsService(paths, Catalog()))) as client:
        response = client.put("/api/settings/execution", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert not paths.home.exists()


def test_same_origin_security_applies_to_execution_selection(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    app = create_app(execution_settings=ExecutionSettingsService(paths, Catalog()), enforce_local_security=True)
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.put("/api/settings/execution", headers={"Origin": "https://evil.example"}, json={"loopId": "standard", "policyId": "no_recovery"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert not paths.home.exists()


def test_corrupt_store_http_error_is_sanitized(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    paths.config_dir.mkdir(parents=True)
    paths.execution_settings_file.write_text("private", encoding="utf-8")
    with TestClient(create_app(execution_settings=ExecutionSettingsService(paths, Catalog()))) as client:
        response = client.get("/api/settings/execution")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "settings_store_unavailable", "message": "Execution settings are unavailable.", "retryable": True}}
