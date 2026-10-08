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
    assert json.loads(store._path.read_text())["version"] == 11


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
            request = ModelRequest(provider, model, mode, (ModelMessage("user", "hello"),), reasoning_resolution=resolve_response_mode(mode, supported))
            for _ in range(2):  # the same decision survives subsequent continuation calls
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
