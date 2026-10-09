"""Single selection, revision conflicts, inert migration, and HTTP boundaries."""
import asyncio
import json
import os
from dataclasses import replace
from importlib.metadata import entry_points
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from opensprite_backend.agent.plugin_catalog import ExecutionPluginCatalog, ExecutionPluginError, PluginDescriptor
from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.execution_settings import ExecutionSettingsError, ExecutionSettingsService
from test_execution_plugin_catalog import InstalledPoint, LOOPS

class Catalog:
    def __init__(self):
        self.items = ExecutionPluginCatalog().descriptors()
        self.validated = []
    def descriptors(self): return self.items
    def validate_selection(self, identifier):
        self.validated.append(identifier)
        item = next((x for x in self.items if x.id == identifier), None)
        if item is None: raise ExecutionPluginError("invalid_request")
        if item.status != "available": raise ExecutionPluginError("plugin_unavailable")

def setup(tmp_path, catalog=None):
    paths = build_app_paths(tmp_path / ".opensprite")
    return paths, ExecutionSettingsService(paths, catalog or Catalog())


def test_defaults_are_lazy_and_saving_never_loads_python(tmp_path):
    point = InstalledPoint("untrusted_until_admission", LOOPS, RuntimeError("must not load"))
    paths, service = setup(tmp_path, ExecutionPluginCatalog((*entry_points().select(group=LOOPS), point)))
    initial = asyncio.run(service.get())
    assert initial.selection.plugin_id == "standard" and initial.revision == 0
    assert service.selection() == "standard" and not paths.home.exists()
    saved = asyncio.run(service.update(point.name, 0))
    assert saved.selection.plugin_id == point.name and saved.revision == 1
    assert service.selection() == point.name and point.loads == 0
    assert json.loads(paths.execution_settings_file.read_bytes()) == {"version": 2, "revision": 1, "pluginId": point.name}
    if os.name != "nt":
        assert paths.config_dir.stat().st_mode & 0o777 == 0o700
        assert paths.execution_settings_file.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("policy", ["standard", "no_recovery"])
def test_known_builtin_pair_migrates_once_and_atomically(tmp_path, policy):
    paths, service = setup(tmp_path)
    paths.config_dir.mkdir(parents=True)
    paths.execution_settings_file.write_text(json.dumps({"version": 1, "loopId": "standard", "policyId": policy}))
    first = asyncio.run(service.get())
    before = paths.execution_settings_file.read_bytes()
    assert first.selection.plugin_id == policy and first.revision == 1 and first.migration is None
    assert asyncio.run(service.get()) == first and paths.execution_settings_file.read_bytes() == before
    assert json.loads(before) == {"version": 2, "revision": 1, "pluginId": policy}


@pytest.mark.parametrize("pair", [("custom", "standard"), ("standard", "custom"), ("custom", "custom")])
def test_external_pair_is_preserved_and_blocks_admission_until_explicit_choice(tmp_path, pair):
    paths, service = setup(tmp_path)
    paths.config_dir.mkdir(parents=True)
    old = json.dumps({"version": 1, "loopId": pair[0], "policyId": pair[1]}).encode()
    paths.execution_settings_file.write_bytes(old)
    state = asyncio.run(service.get())
    assert state.selection is None and state.revision == 0
    assert (state.migration.loopId, state.migration.policyId) == pair
    assert paths.execution_settings_file.read_bytes() == old
    with pytest.raises(ExecutionSettingsError, match="migration_required"): service.selection()
    saved = asyncio.run(service.update("no_recovery", 0))
    assert saved.selection.plugin_id == "no_recovery" and saved.migration is None
    assert service.selection() == "no_recovery"


def test_concurrent_writes_have_one_winner_and_keep_loser_draft_out_of_storage(tmp_path):
    paths, service = setup(tmp_path)
    async def writes():
        return await asyncio.gather(service.update("standard", 0), service.update("no_recovery", 0), return_exceptions=True)
    results = asyncio.run(writes())
    errors = [x for x in results if isinstance(x, ExecutionSettingsError)]
    winners = [x for x in results if not isinstance(x, Exception)]
    assert len(winners) == len(errors) == 1 and errors[0].code == "revision_conflict"
    assert service.selection() == winners[0].selection.plugin_id
    assert json.loads(paths.execution_settings_file.read_bytes())["revision"] == 1


@pytest.mark.parametrize("payload", ["not-json", "null", "{}", '{"version":true,"pluginId":"standard","revision":1}',
    '{"version":2,"pluginId":"standard","revision":true}', '{"version":2,"pluginId":"../x","revision":1}',
    '{"version":2,"pluginId":"standard","revision":0}', '{"version":2,"pluginId":"standard","revision":1,"extra":1}',
    '{"version":2,"pluginId":"standard","pluginId":"standard","revision":1}', " " * (1024 * 1024 + 1)], ids=lambda value: "oversized" if len(value) > 200 else value)
def test_corrupt_settings_are_sanitized_and_not_overwritten(tmp_path, payload):
    paths, service = setup(tmp_path)
    paths.config_dir.mkdir(parents=True)
    paths.execution_settings_file.write_text(payload)
    with pytest.raises(ExecutionSettingsError) as failure: asyncio.run(service.get())
    assert failure.value.code == "settings_store_unavailable" and failure.value.__context__ is None
    with pytest.raises(ExecutionSettingsError): asyncio.run(service.update("standard", 0))
    assert paths.execution_settings_file.read_text() == payload


def test_missing_saved_plugin_is_visible_and_can_be_replaced(tmp_path):
    paths, service = setup(tmp_path)
    paths.config_dir.mkdir(parents=True)
    paths.execution_settings_file.write_text('{"version":2,"pluginId":"removed","revision":8}')
    assert asyncio.run(service.get()).selection.plugin_id == "removed"
    with pytest.raises(ExecutionSettingsError, match="invalid_request"): service.selection()
    assert asyncio.run(service.update("standard", 8)).revision == 9


def test_write_failure_preserves_bytes_and_cleans_staging(tmp_path, monkeypatch):
    paths, service = setup(tmp_path)
    asyncio.run(service.update("standard", 0))
    before = paths.execution_settings_file.read_bytes()
    def fail(*args): raise OSError("private secret path")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(ExecutionSettingsError) as failure: asyncio.run(service.update("no_recovery", 1))
    assert failure.value.__context__ is None and "private" not in str(failure.value)
    assert paths.execution_settings_file.read_bytes() == before and list(paths.config_dir.glob("*.tmp")) == []


def test_broken_catalog_does_not_create_settings(tmp_path):
    catalog = Catalog(); catalog.items += (catalog.items[0],)
    paths, service = setup(tmp_path, catalog)
    with pytest.raises(ExecutionSettingsError, match="plugin_unavailable"): asyncio.run(service.update("standard", 0))
    assert not paths.home.exists()


def test_http_single_selection_and_revision_conflict(tmp_path):
    paths, service = setup(tmp_path)
    with TestClient(create_app(execution_settings=service)) as client:
        initial = client.get("/api/settings/execution")
        assert initial.status_code == 200 and initial.json()["revision"] == 0
        assert initial.json()["selection"] == {"pluginId": "standard"}
        saved = client.put("/api/settings/execution", json={"pluginId": "no_recovery", "expectedRevision": 0})
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        conflict = client.put("/api/settings/execution", json={"pluginId": "standard", "expectedRevision": 0})
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "revision_conflict"
        invalid = client.put("/api/settings/execution", json={"pluginId": "unknown", "expectedRevision": 1})
        assert invalid.status_code == 400
    assert service.selection() == "no_recovery"


@pytest.mark.parametrize("payload", [{}, {"pluginId": "standard"}, {"pluginId": True, "expectedRevision": 0},
    {"pluginId": "standard", "expectedRevision": True}, {"loopId": "standard", "policyId": "standard"},
    {"pluginId": "standard", "expectedRevision": 0, "extra": True}])
def test_http_rejects_noncanonical_requests(tmp_path, payload):
    paths, service = setup(tmp_path)
    with TestClient(create_app(execution_settings=service)) as client:
        assert client.put("/api/settings/execution", json=payload).status_code == 400
    assert not paths.home.exists()


def test_same_origin_security_still_applies(tmp_path):
    paths, service = setup(tmp_path)
    with TestClient(create_app(execution_settings=service, enforce_local_security=True), base_url="http://localhost:8765") as client:
        response = client.put("/api/settings/execution", headers={"Origin": "https://evil.example"}, json={"pluginId":"no_recovery", "expectedRevision":0})
        assert response.status_code == 400
    assert not paths.home.exists()
