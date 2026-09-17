"""Response levels, provider payloads, immutable decisions and v18 upgrades."""

import asyncio
from contextlib import closing
import json
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
import httpx
import pytest

from opensprite_backend.ai_settings import AiSettingsService, JsonAiSettingsStore, SettingsStoreError
from opensprite_backend.app import create_app
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.conversations.sqlite_schema import SCHEMA_SQL
from opensprite_backend.conversations.response_mode_migration import OLD_CHECK, NEW_CHECK, RESOLUTION_COLUMN, migrate
from opensprite_backend.inference.anthropic import AnthropicInferenceAdapter
from opensprite_backend.inference.models import ModelMessage, ModelRequest
from opensprite_backend.inference.openai import OpenAIInferenceAdapter
from opensprite_backend.inference.openrouter import OpenRouterInferenceAdapter
from opensprite_backend.providers.openrouter_models import OpenRouterModelDiscovery
from opensprite_backend.response_modes import RESPONSE_MODES, ReasoningResolution, resolve_response_mode
from test_ai_settings import RecordingConnections
from test_inference_adapters import response


@pytest.mark.parametrize("mode", RESPONSE_MODES)
def test_modes_round_trip_and_reject_retired_writes(tmp_path, mode):
    store = JsonAiSettingsStore(tmp_path / "settings.json")
    with TestClient(create_app(RecordingConnections(), ai_settings=AiSettingsService(store, RecordingConnections()))) as client:
        payload = {"model": None, "responseMode": mode, "outputContinuation": "5", "responseDelivery": "stream", "logFullPrompts": False}
        assert client.put("/api/settings/ai", json=payload).status_code == 200
        assert client.get("/api/settings/ai").json()["responseMode"] == mode
        for old in ("fast", "balanced", "deep", "medim"):
            assert client.put("/api/settings/ai", json={**payload, "responseMode": old}).status_code == 400
    assert JsonAiSettingsStore(store._path).get().responseMode == mode
    assert json.loads(store._path.read_text())["version"] == 10


@pytest.mark.parametrize(("old", "new"), [("default", "default"), ("fast", "low"), ("balanced", "medium"), ("deep", "high")])
def test_v9_read_migration_preserves_file_and_policies(tmp_path, old, new):
    path = tmp_path / "settings.json"
    payload = {"version": 9, "model": None, "responseMode": old, "outputContinuation": "5", "responseDelivery": "complete", "logFullPrompts": False, "providerToolPolicies": {"openai": {"toolsEnabled": False, "transport": "stream", "disabledModels": []}}}
    path.write_text(json.dumps(payload))
    before = path.read_bytes()
    store = JsonAiSettingsStore(path)
    result = store.get()
    assert result.responseMode == new
    assert not result.providerToolPolicies["openai"].toolsEnabled
    assert path.read_bytes() == before
    path.write_text(json.dumps({**payload, "version": 10}))
    if old == "default":
        assert store.get().responseMode == "default"
    else:
        with pytest.raises(SettingsStoreError):
            store.get()


def test_highest_fallback_is_not_nearest_and_unknown_is_not_unsupported():
    assert resolve_response_mode("low", ("medium", "high")).effective == "high"
    assert resolve_response_mode("xhigh", ("low", "medium", "high", "max")).effective == "max"
    assert resolve_response_mode("ultra", None).status == "unknown"
    assert resolve_response_mode("ultra", ()).status == "provider_default"


def test_default_preview_never_queries_provider_capabilities(tmp_path):
    class UnavailableConnections:
        async def list_openrouter_models(self):
            pytest.fail("Default must not query provider capabilities")

    service = AiSettingsService(JsonAiSettingsStore(tmp_path / "settings.json"), UnavailableConnections())
    with TestClient(create_app(ai_settings=service)) as client:
        result = client.get("/api/settings/ai/response-mode", params={"providerId": "openrouter", "modelId": "any/model", "responseMode": "default"})
        assert result.status_code == 200
        assert result.json() == {"requested": "default", "effective": None, "status": "provider_default"}


def test_current_settings_keep_an_existing_explicit_level(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 10, "model": None, "responseMode": "medium", "outputContinuation": "5", "responseDelivery": "stream", "logFullPrompts": False, "providerToolPolicies": {}}))
    assert JsonAiSettingsStore(path).get().responseMode == "medium"


@pytest.mark.parametrize("mode", RESPONSE_MODES)
@pytest.mark.parametrize(("provider", "model", "supported"), [
    ("openai", "gpt-5.6", ("low", "medium", "high", "xhigh", "max")),
    ("anthropic", "claude-sonnet-4-6", ("low", "medium", "high", "max")),
    ("openrouter", "test/model", ("low", "medium", "high")),
    ("openai", "gpt-5.6", None),
    ("anthropic", "claude-haiku-4-5", ()),
    ("openrouter", "test/model", None),
])
def test_adapter_payload_matches_resolved_level(provider, model, supported, mode):
    captured = []
    def handler(outbound):
        captured.append(json.loads(outbound.content))
        if provider == "openai":
            return response(outbound, {"type": "response.completed", "response": {"status": "completed", "output": [], "usage": None}})
        if provider == "anthropic":
            return response(outbound, {"type": "message_start", "message": {"usage": {"input_tokens": 1}}}, {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}}, {"type": "message_stop"})
        return response(outbound, {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}, "[DONE]")
    expected = None if mode == "default" or not supported else mode if mode in supported else supported[-1]
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = {"openai": OpenAIInferenceAdapter, "anthropic": AnthropicInferenceAdapter, "openrouter": OpenRouterInferenceAdapter}[provider](client)
            request = ModelRequest(provider, model, mode, (ModelMessage("user", "hello"),), (), reasoning_resolution=resolve_response_mode(mode, supported))
            for _ in range(2):  # the same decision survives subsequent tool/continuation calls
                async for _event in adapter.stream(request, "test-key"):
                    pass
    asyncio.run(scenario())
    for body in captured:
        parameter = "output_config" if provider == "anthropic" else "reasoning"
        if expected is None:
            assert parameter not in body
        else:
            assert body[parameter]["effort"] == expected


def test_preview_has_no_settings_write_and_matches_capability(tmp_path):
    store = JsonAiSettingsStore(tmp_path / "settings.json")
    service = AiSettingsService(store, RecordingConnections())
    with TestClient(create_app(RecordingConnections(), ai_settings=service)) as client:
        for model, expected, status in [("gpt-5.6", "max", "fallback"), ("unknown-model", None, "unknown")]:
            result = client.get("/api/settings/ai/response-mode", params={"providerId": "openai", "modelId": model, "responseMode": "ultra"})
            assert result.status_code == 200
            assert result.json() == {"requested": "ultra", "effective": expected, "status": status}
        assert client.get("/api/settings/ai/response-mode", params={"providerId": "openai", "modelId": "gpt-5.6", "responseMode": "medim"}).status_code == 400
    assert not store._path.exists()


@pytest.mark.parametrize(("reasoning", "expected"), [(None, ()), ({}, ()), ({"supported_efforts": None}, ("none", "minimal", "low", "medium", "high", "xhigh", "max")), ({"supported_efforts": ["high", "low"]}, ("high", "low")), ({"supported_efforts": ["invented"]}, None)])
def test_openrouter_discovery_preserves_capability_states(reasoning, expected):
    model = OpenRouterModelDiscovery._usable_model({"id": "test/model", "name": "Test", "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}, "context_length": 32000, "reasoning": reasoning})
    assert model.reasoning_efforts == expected


@pytest.mark.parametrize(("old_mode", "expected_mode"), [("default", "default"), ("fast", "low"), ("balanced", "medium"), ("deep", "high")])
def test_v18_upgrade_preserves_history_and_freezes_new_resolution(tmp_path, old_mode, expected_mode):
    # Seed real current data, then copy into the actual preceding table definition.
    source = SqliteConversationRepository(tmp_path / "source.db")
    old = source.start_run(conversation_id=None, client_request_id=str(uuid4()), message="old", provider_id="openai", model_id="gpt-5.6", response_mode="deep")
    source.mark_run_started(old.run.id)
    source.complete_run(old.run.id, "answer")
    path = tmp_path / "upgrade.db"
    old_schema = SCHEMA_SQL.replace(NEW_CHECK, OLD_CHECK).replace("ALTER TABLE runs ADD COLUMN " + RESOLUTION_COLUMN + ";\n", "").replace("PRAGMA user_version = 19", "PRAGMA user_version = 18")
    with closing(sqlite3.connect(path)) as target, closing(sqlite3.connect(tmp_path / "source.db")) as original:
        target.executescript(old_schema)
        for table in ("conversations", "messages", "runs", "run_events"):
            columns = [row[1] for row in target.execute(f"PRAGMA table_info({table})")]
            names = ",".join(columns)
            target.executemany(f"INSERT INTO {table} ({names}) VALUES ({','.join('?' for _ in columns)})", original.execute(f"SELECT {names} FROM {table}"))
        target.execute("INSERT INTO schedules(id,name,prompt,cadence_type,local_time,time_zone,provider_id,model_id,response_mode,context_budget,output_budget,output_continuation,status,revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (str(uuid4()), "old schedule", "hello", "daily", "09:00", "UTC", "openai", "gpt-5.6", old_mode, "auto", "auto", "5", "paused", 1, "2026-09-17T00:00:00Z", "2026-09-17T00:00:00Z"))
        target.commit()
    upgraded = SqliteConversationRepository(path)
    upgraded.interrupt_incomplete_runs()
    assert upgraded.get_run(old.run.id).response_mode == "deep"
    assert upgraded.get_run(old.run.id).reasoning_resolution is None
    assert upgraded.list_run_events(old.run.id, after_sequence=0, limit=100) == source.list_run_events(old.run.id, after_sequence=0, limit=100)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 19
        assert connection.execute("SELECT response_mode FROM schedules").fetchone()[0] == expected_mode
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    run = upgraded.start_run(conversation_id=old.run.conversation_id, client_request_id=str(uuid4()), message="new", provider_id="openai", model_id="gpt-5.6", response_mode="ultra").run
    upgraded.mark_run_started(run.id)
    resolution = resolve_response_mode("ultra", ("low", "high"))
    upgraded.set_reasoning_resolution(run.id, resolution)
    assert upgraded.set_reasoning_resolution(run.id, resolve_response_mode("ultra", ("max",))).reasoning_resolution == resolution
    assert SqliteConversationRepository(path).get_run(run.id).reasoning_resolution == resolution


def test_migration_failure_rolls_back_tables_and_version(tmp_path):
    connection = sqlite3.connect(tmp_path / "rollback.db", isolation_level=None)
    old_schema = SCHEMA_SQL.replace(NEW_CHECK, OLD_CHECK).replace("ALTER TABLE runs ADD COLUMN " + RESOLUTION_COLUMN + ";\n", "").replace("PRAGMA user_version = 19", "PRAGMA user_version = 18")
    connection.executescript(old_schema)
    before = connection.execute("SELECT sql FROM sqlite_master WHERE name='runs'").fetchone()[0]
    connection.set_authorizer(lambda action, arg, *_: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_DROP_TABLE and arg == "schedules" else sqlite3.SQLITE_OK)
    with pytest.raises(sqlite3.DatabaseError):
        migrate(connection)
    connection.set_authorizer(None)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 18
    assert connection.execute("SELECT sql FROM sqlite_master WHERE name='runs'").fetchone()[0] == before
    assert connection.execute("SELECT name FROM sqlite_master WHERE name LIKE '%_v19'").fetchall() == []
    connection.close()
