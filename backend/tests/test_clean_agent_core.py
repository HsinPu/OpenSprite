"""Clean-core boundaries, provider wire behavior and non-destructive upgrades."""

import asyncio
from contextlib import closing
from importlib.util import find_spec
import json
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import httpx
import pytest

from execution_package_test_support import FILE_NAME, INFO, MODULE, paths, wheel
from test_inference_adapters import response
from opensprite_backend.app import create_app
from opensprite_backend.ai_settings import JsonAiSettingsStore
from opensprite_backend.conversations.models import RunEventType
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.conversations.sqlite_schema import SCHEMA_SQL, migrate_schema
from opensprite_backend.execution_plugins.inspection import inspect_wheel
from opensprite_backend.execution_plugins.models import ExecutionPackageError
from opensprite_backend.execution_plugins.service import ExecutionPackageService
from opensprite_backend.execution_plugins.store import ExecutionPackageStore
from opensprite_backend.inference.anthropic import AnthropicInferenceAdapter
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import InferenceFailure, ModelCompleted, ModelFinishReason, ModelMessage, ModelRequest, ModelTextDelta
from opensprite_backend.inference.openai import OpenAIInferenceAdapter
from opensprite_backend.inference.openrouter import OpenRouterInferenceAdapter
from opensprite_backend.models import AiSettings


@pytest.mark.parametrize("url", [
    "/api/tools", "/api/settings/tools", "/api/skills", "/api/skills/settings",
    "/api/agents", "/api/agents/settings", "/api/mcp/servers", "/api/schedules",
    "/api/tool-approvals/11111111-1111-4111-8111-111111111111",
    "/api/runs/11111111-1111-4111-8111-111111111111/agents",
    "/api/settings/ai/providers/openai/tools",
])
def test_retired_http_surfaces_are_absent(url):
    with TestClient(create_app()) as client:
        for method in (client.get, client.post, client.put, client.delete):
            assert method(url).status_code == 404


@pytest.mark.parametrize("package", ["tools", "skills", "custom_agents", "mcp", "schedules", "tool_settings"])
def test_retired_runtime_packages_cannot_be_imported(package):
    assert find_spec("opensprite_backend." + package) is None


def text_frames(provider, text):
    if provider == "openai":
        return [
            {"type": "response.output_item.added", "item": {"type": "message"}},
            {"type": "response.reasoning_text.delta", "delta": "hidden fixture reasoning"},
            {"type": "response.output_text.delta", "delta": text},
            {"type": "response.output_item.done", "item": {"type": "message"}},
            {"type": "response.completed", "response": {"status": "completed", "output": [{"type": "message"}], "usage": {"input_tokens": 9, "output_tokens": 5}}},
        ]
    if provider == "anthropic":
        return [
            {"type": "message_start", "message": {"usage": {"input_tokens": 9}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 5}},
            {"type": "message_stop"},
        ]
    return [
        {"choices": [{"index": 0, "delta": {"content": text, "reasoning": "hidden fixture reasoning"}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 9, "completion_tokens": 5}},
        "[DONE]",
    ]


ADAPTERS = {"openai": OpenAIInferenceAdapter, "anthropic": AnthropicInferenceAdapter, "openrouter": OpenRouterInferenceAdapter}


@pytest.mark.parametrize("provider", ADAPTERS)
def test_native_text_protocol_echoes_variable_input_without_advertising_actions(provider):
    nonce = str(uuid4())
    sent = []
    def handle(outbound):
        body = json.loads(outbound.content)
        sent.append(body)
        messages = body.get("input", body.get("messages"))
        assert messages[-1] == {"role": "user", "content": nonce}
        assert not {"tools", "tool_choice", "functions", "function_call"}.intersection(body)
        assert body["stream"] is True
        return response(outbound, *text_frames(provider, "echo " + messages[-1]["content"]))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            request = ModelRequest(provider, "fixture/model", "default", (ModelMessage("user", nonce),))
            return [item async for item in ADAPTERS[provider](client).stream(request, "isolated-token")]
    events = asyncio.run(scenario())
    assert "".join(item.text for item in events if isinstance(item, ModelTextDelta)) == "echo " + nonce
    assert events[-1] == ModelCompleted(ModelFinishReason.FINAL)
    assert len(sent) == 1 and "hidden fixture reasoning" not in repr(events)


@pytest.mark.parametrize("provider,frame", [
    ("openai", {"type": "response.output_item.added", "item": {"type": "function_call", "name": "legacy_action"}}),
    ("openai", {"type": "response.output_item.done", "item": {"type": "function_call"}}),
    ("openai", {"type": "response.function_call_arguments.delta", "delta": "{}"}),
    ("openai", {"type": "response.completed", "response": {"status": "completed", "output": [{"type": "function_call"}]}}),
    ("anthropic", {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "name": "legacy_action"}}),
    ("anthropic", {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "{}"}}),
    ("openrouter", {"choices": [{"index": 0, "delta": {"tool_calls": [{"function": {"name": "legacy_action"}}]}, "finish_reason": None}]}),
    ("openrouter", {"choices": [{"index": 0, "delta": {"function_call": {"name": "legacy_action"}}, "finish_reason": None}]}),
])
def test_unsupported_provider_actions_fail_closed_without_success(provider, frame):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda outbound: response(outbound, frame))) as client:
            request = ModelRequest(provider, "fixture/model", "default", (ModelMessage("user", str(uuid4())),))
            emitted = []
            with pytest.raises(ModelGatewayError) as failure:
                async for item in ADAPTERS[provider](client).stream(request, "isolated-token"):
                    emitted.append(item)
            assert failure.value.failure is InferenceFailure.INVALID_PROVIDER_RESPONSE
            assert not any(isinstance(item, ModelCompleted) for item in emitted)
    asyncio.run(scenario())


def test_fresh_database_has_only_core_tables_and_no_action_or_schedule_columns(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "core.sqlite")
    repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message="text",
                         provider_id="openai", model_id="fixture", response_mode="default")
    with closing(sqlite3.connect(repository.database_file)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
        assert tables == {"conversations", "messages", "runs", "run_events", "run_steps", "conversation_compactions"}
        assert not {"source", "occurrence_id"}.intersection(columns)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 23


def test_v20_upgrade_preserves_inert_tables_and_projects_only_core_events(tmp_path):
    database = tmp_path / "legacy.sqlite"
    baseline = Path(__file__).parent / "fixtures" / "core_schema_v20.sql"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(baseline.read_text(encoding="utf-8"))
        connection.execute("CREATE TABLE preserved_fixture (payload TEXT)")
        connection.execute("INSERT INTO preserved_fixture VALUES ('opaque legacy state')")
        connection.commit()
    repository = SqliteConversationRepository(database)
    run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message="after upgrade",
                               provider_id="openai", model_id="fixture", response_mode="default").run
    timestamp = run.created_at.isoformat().replace("+00:00", "Z")
    with closing(sqlite3.connect(database)) as connection:
        rows = [
            (run.id, 1, "execution.selected", json.dumps({"loopId": "standard", "loopVersion": "1.0.0", "policyId": "standard", "policyVersion": "1.0.0", "apiVersion": 1}), timestamp),
            (run.id, 2, "tool.started", json.dumps({"toolName": "legacy_action"}), timestamp),
            (run.id, 3, "model.started", json.dumps({"providerId": "openai", "modelId": "fixture", "responseMode": "default", "maxOutputTokens": 4096, "toolNames": ["legacy_action"]}), timestamp),
            (run.id, 4, "assistant.delta", json.dumps({"text": "visible historical text"}), timestamp),
        ]
        connection.executemany("INSERT INTO run_events VALUES (?, ?, ?, ?, ?)", rows)
        connection.commit()
        before = connection.execute("SELECT * FROM run_events ORDER BY sequence").fetchall()
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 23
        assert connection.execute("SELECT payload FROM preserved_fixture").fetchone()[0] == "opaque legacy state"
    page = repository.list_run_events(run.id, after_sequence=0, limit=1)
    assert page[0].sequence == 3 and "toolNames" not in page[0].data
    assert repository.list_run_events(run.id, after_sequence=3, limit=1)[0].data == {"text": "visible historical text"}
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT * FROM run_events ORDER BY sequence").fetchall() == before


def test_incomplete_v20_upgrade_refuses_to_advance_version():
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("PRAGMA user_version = 20")
        with pytest.raises(ValueError, match="Incomplete"):
            migrate_schema(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 20


def test_old_ai_settings_are_read_without_write_and_next_save_has_no_tool_policy(tmp_path):
    path = tmp_path / "settings.json"
    old = {"version": 10, "model": None, "responseMode": "high", "outputContinuation": "2",
           "responseDelivery": "stream", "logFullPrompts": False, "providerToolPolicies": {"openai": {"enabled": True, "nonStreaming": True}}}
    path.write_text(json.dumps(old), encoding="utf-8")
    before = path.read_bytes()
    store = JsonAiSettingsStore(path)
    settings = store.get()
    assert settings.responseMode.value == "high" and json.loads(path.read_bytes())["version"] == 12
    store.set(AiSettings(**settings.model_dump()))
    saved = json.loads(path.read_bytes())
    assert saved["version"] == 12 and "providerToolPolicies" not in saved
    assert store.get() == settings


def test_retired_cached_wheel_is_readable_but_cannot_be_imported_or_deployed(tmp_path):
    data = wheel(changes={INFO + "/entry_points.txt": f"[opensprite_backend.agent_loops.v1]\nfixture_loop = {MODULE}:factory\n".encode()})
    store = ExecutionPackageStore(paths(tmp_path))
    # Seed a cache that was validated by the preceding release; no import executes.
    old = inspect_wheel(data, FILE_NAME, allow_retired_api=True)
    stored = store.save(old, data)
    service = ExecutionPackageService(paths(tmp_path), base_image_ref="opensprite:fixture", runtime_kind="docker")
    assert service.list().packages[0].plugins[0].apiVersion == 1
    assert store.get(stored.id)[1] == data
    with pytest.raises(ExecutionPackageError, match="incompatible_package"):
        service.import_wheel(FILE_NAME, data)
    with pytest.raises(ExecutionPackageError, match="incompatible_package"):
        service.bundle(stored.id)
    assert MODULE not in sys.modules and store.get(stored.id)[1] == data


def test_legacy_provider_catalog_preserves_file_bytes_and_core_model_settings(tmp_path):
    from opensprite_backend.credentials import EncryptedJsonCredentialStore
    from opensprite_backend.providers.catalog_store import CustomModel, JsonProviderCatalog
    from opensprite_backend.providers.catalog_transaction import ProviderCatalogTransaction
    from opensprite_backend.providers.custom_service import CustomProviderService

    path = tmp_path / "providers.json"
    service = CustomProviderService(ProviderCatalogTransaction(JsonProviderCatalog(path),
        EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key"), tmp_path / "transaction.json"))
    fields = dict(name="Private model", base_url="https://example.com/v1", auth_mode="none", allow_insecure_local=False)
    provider = service.save(provider_id=None, secret=None, expected_revision=0, **fields)
    model = CustomModel(key=str(uuid4()), model_id="variable-model", name="Variable", context_limit=32000, output_limit=4096, source="manual")
    service.save_model(provider.id, model, expected_revision=1)
    raw = json.loads(path.read_bytes())
    raw["providers"][0].update(tools_enabled=True, non_streaming_tools=True)
    raw["providers"][0]["models"][0]["tools"] = True
    path.write_text(json.dumps(raw), encoding="utf-8")
    before = path.read_bytes()
    loaded = service.get(provider.id)
    assert loaded.models == (model,) and path.read_bytes() == before
    assert "tools_enabled" not in loaded.model_dump()
    service.save(provider_id=provider.id, secret=None, expected_revision=2, **fields)
    saved = json.loads(path.read_bytes())["providers"][0]
    assert not {"tools_enabled", "non_streaming_tools"}.intersection(saved)
    assert saved["models"][0]["model_id"] == model.model_id and "tools" not in saved["models"][0]
