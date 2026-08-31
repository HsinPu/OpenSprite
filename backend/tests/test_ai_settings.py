"""Tests for strict, local-only persisted AI settings."""

from __future__ import annotations

from asyncio import run
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.ai_settings import (
    AiSettingsService,
    JsonAiSettingsStore,
    SettingsStoreError,
    create_ai_settings_service,
)
from opensprite_backend.models import (
    AiSettings,
    ErrorCode,
    ModelSelection,
    ProviderListResponse,
    ProviderStatus,
    ProviderSummary,
    ResponseDelivery,
    ResponseMode,
    OutputContinuation,
)
from opensprite_backend.provider_connections import ProviderConnectionError
from opensprite_backend.runtime import create_system_app, create_system_runtime


def selection() -> ModelSelection:
    return ModelSelection(
        providerId="openai",
        modelId="gpt-5.6",
        contextBudget="auto",
        outputBudget="auto",
    )


def settings(
    *,
    model: ModelSelection | None = None,
    response_mode: ResponseMode = ResponseMode.BALANCED,
    output_continuation: OutputContinuation = OutputContinuation.TWO,
    response_delivery: ResponseDelivery = ResponseDelivery.STREAM,
) -> AiSettings:
    return AiSettings(
        model=model,
        responseMode=response_mode,
        outputContinuation=output_continuation,
        responseDelivery=response_delivery,
    )


class RecordingConnections:
    def __init__(self, *, connected: bool = True) -> None:
        self.list_calls = 0
        self.connected = connected

    async def list_providers(self) -> ProviderListResponse:
        self.list_calls += 1
        return ProviderListResponse(
            providers=[
                ProviderSummary(
                    id=provider_id,
                    name=name,
                    connected=self.connected if provider_id == "openai" else False,
                    status=(
                        ProviderStatus.CONNECTED
                        if provider_id == "openai" and self.connected
                        else ProviderStatus.DISCONNECTED
                    ),
                    credentialPreview="••••test"
                    if provider_id == "openai" and self.connected
                    else None,
                    lastCheckedAt="2026-08-20T12:00:00Z"
                    if provider_id == "openai" and self.connected
                    else None,
                )
                for provider_id, name in (
                    ("openai", "OpenAI"),
                    ("anthropic", "Anthropic"),
                    ("openrouter", "OpenRouter"),
                )
            ]
        )


def test_store_round_trip_and_lazy_default_read(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonAiSettingsStore(paths.settings_file)

    assert store.get() == AiSettings(model=None, responseMode="default", outputContinuation="2", responseDelivery="stream")
    assert not paths.home.exists()
    saved = settings(model=selection(), response_mode=ResponseMode.DEEP, response_delivery=ResponseDelivery.COMPLETE)
    store.set(saved)

    assert store.get() == saved
    assert json.loads(paths.settings_file.read_text(encoding="utf-8")) == {
        "version": 8,
        "model": {
            "providerId": "openai",
            "modelId": "gpt-5.6",
            "contextBudget": "auto",
            "outputBudget": "auto",
        },
        "responseMode": "deep",
        "outputContinuation": "2",
        "responseDelivery": "complete",
        "logFullPrompts": False,
    }
    assert sorted(path.relative_to(paths.home).as_posix() for path in paths.home.rglob("*")) == [
        "config",
        "config/settings.json",
    ]

    cleared = settings(model=None, response_mode=ResponseMode.FAST)
    store.set(cleared)
    assert store.get() == cleared
    assert paths.settings_file.exists()


def test_store_reads_current_v3_selection_as_auto_output_without_rewriting(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    previous = (
        b'{"version":3,"model":{"providerId":"openai",'
        b'"modelId":"gpt-5.6","contextBudget":"auto"},"responseMode":"balanced"}'
    )
    path.write_bytes(previous)

    assert JsonAiSettingsStore(path).get() == settings(
        model=selection(),
        response_mode=ResponseMode.BALANCED,
    )
    assert path.read_bytes() == previous


def test_store_reads_v3_null_model_without_rewriting(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    previous = b'{"version":3,"model":null,"responseMode":"deep"}'
    path.write_bytes(previous)

    assert JsonAiSettingsStore(path).get() == settings(
        model=None,
        response_mode=ResponseMode.DEEP,
    )
    assert path.read_bytes() == previous


def test_store_reads_v4_as_auto_continue_without_rewriting(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    previous = (
        b'{"version":4,"model":{"providerId":"openai",'
        b'"modelId":"gpt-5.6","contextBudget":"auto",'
        b'"outputBudget":"auto"},"responseMode":"balanced"}'
    )
    path.write_bytes(previous)

    assert JsonAiSettingsStore(path).get() == settings(model=selection())
    assert path.read_bytes() == previous


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [(True, OutputContinuation.TWO), (False, OutputContinuation.OFF)],
)
def test_store_reads_v6_boolean_continuation_without_rewriting(
    tmp_path: Path,
    enabled: bool,
    expected: OutputContinuation,
) -> None:
    path = tmp_path / "settings.json"
    previous = json.dumps(
        {
            "version": 6,
            "model": None,
            "responseMode": "balanced",
            "autoContinueOutput": enabled,
            "logFullPrompts": False,
        },
        separators=(",", ":"),
    ).encode()
    path.write_bytes(previous)

    assert JsonAiSettingsStore(path).get() == settings(output_continuation=expected)
    assert path.read_bytes() == previous


def test_store_reads_v7_without_response_delivery_as_stream_without_rewriting(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    previous = json.dumps(
        {
            "version": 7,
            "model": None,
            "responseMode": "balanced",
            "outputContinuation": "2",
            "logFullPrompts": False,
        },
        separators=(",", ":"),
    ).encode()
    path.write_bytes(previous)

    assert JsonAiSettingsStore(path).get() == settings()
    assert path.read_bytes() == previous


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":8,"model":null,"responseMode":"balanced","outputContinuation":"2","responseDelivery":"stream","logFullPrompts":false,"extra":true}',
        '{"version":8,"version":8,"model":null,"responseMode":"balanced","outputContinuation":"2","responseDelivery":"stream","logFullPrompts":false}',
        '{"version":3,"model":{"providerId":"openai","modelId":"gpt-5.6","contextBudget":"auto","extra":true},"responseMode":"balanced"}',
        '{"version":1,"defaultModel":{"providerId":"openai","modelId":"gpt-5.6"}}',
        '{"version":8,"model":{"providerId":"other","modelId":"gpt-5.6","contextBudget":"auto","outputBudget":"auto"},"responseMode":"balanced","outputContinuation":"2","responseDelivery":"stream","logFullPrompts":false}',
        '{"version":8,"model":{"providerId":"openai","modelId":"   ","contextBudget":"auto","outputBudget":"auto"},"responseMode":"balanced","outputContinuation":"2","responseDelivery":"stream","logFullPrompts":false}',
        '{"version":8,"model":{"providerId":"openai","modelId":"gpt-5.6","contextBudget":"other","outputBudget":"auto"},"responseMode":"balanced","outputContinuation":"2","responseDelivery":"stream","logFullPrompts":false}',
        '{"version":8,"model":{"providerId":"openai","modelId":"gpt-5.6","contextBudget":"auto","outputBudget":"other"},"responseMode":"balanced","outputContinuation":"2","responseDelivery":"stream","logFullPrompts":false}',
        '{"version":8,"model":null,"responseMode":"other","outputContinuation":"2","responseDelivery":"stream","logFullPrompts":false}',
        '{"version":8,"model":null,"responseMode":"balanced","outputContinuation":"other","responseDelivery":"stream","logFullPrompts":false}',
        '{"version":8,"model":null,"responseMode":"balanced","outputContinuation":"2","responseDelivery":"other","logFullPrompts":false}',
    ],
)
def test_store_rejects_malformed_or_noncanonical_json(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(SettingsStoreError) as raised:
        JsonAiSettingsStore(path).get()

    assert str(raised.value) == "AI settings are unavailable."
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_store_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(SettingsStoreError):
        JsonAiSettingsStore(path).get()


def test_atomic_failure_cleans_temp_and_preserves_old_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config" / "settings.json"
    store = JsonAiSettingsStore(path)
    store.set(settings(model=selection()))
    before = path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("private replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(SettingsStoreError) as raised:
        store.set(
            settings(
                model=ModelSelection(
                    providerId="anthropic",
                    modelId="claude",
                    contextBudget="128k",
                    outputBudget="32k",
                )
            )
        )

    assert str(raised.value) == "AI settings are unavailable."
    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_service_checks_connection_only_for_non_null_model(
    tmp_path: Path,
) -> None:
    connections = RecordingConnections(connected=False)
    service = AiSettingsService(
        JsonAiSettingsStore(tmp_path / "settings.json"),
        connections,
    )

    with pytest.raises(ProviderConnectionError) as raised:
        run(service.put(settings(model=selection())))
    assert raised.value.code is ErrorCode.NOT_CONNECTED
    assert connections.list_calls == 1

    response = run(service.put(settings(model=None, response_mode=ResponseMode.DEEP)))
    assert response == settings(model=None, response_mode=ResponseMode.DEEP)
    assert connections.list_calls == 1


def test_api_routes_return_ai_settings_and_map_errors(tmp_path: Path) -> None:
    connections = RecordingConnections()
    service = AiSettingsService(
        JsonAiSettingsStore(tmp_path / "settings.json"),
        connections,
    )
    with TestClient(create_app(connections, ai_settings=service)) as client:
        initial = client.get("/api/settings/ai")
        saved = client.put(
            "/api/settings/ai",
            json={"model": {"providerId": "openai", "modelId": "gpt-5.6", "contextBudget": "128k", "outputBudget": "32k"}, "responseMode": "deep", "outputContinuation": "5", "responseDelivery": "complete", "logFullPrompts": True},
        )
        invalid = client.put(
            "/api/settings/ai",
            json={"model": {"providerId": "openai", "modelId": "   ", "contextBudget": "auto", "outputBudget": "auto"}, "responseMode": "deep", "outputContinuation": "2", "responseDelivery": "stream", "logFullPrompts": False},
        )

    assert initial.json() == {"model": None, "responseMode": "default", "outputContinuation": "2", "responseDelivery": "stream", "logFullPrompts": False}
    assert saved.status_code == 200
    assert saved.json() == {
        "model": {"providerId": "openai", "modelId": "gpt-5.6", "contextBudget": "128k", "outputBudget": "32k"},
        "responseMode": "deep",
        "outputContinuation": "5",
        "responseDelivery": "complete",
        "logFullPrompts": True,
    }
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_request"


def test_same_origin_protection_applies_to_ai_settings_put(tmp_path: Path) -> None:
    connections = RecordingConnections()
    service = AiSettingsService(
        JsonAiSettingsStore(tmp_path / "settings.json"),
        connections,
    )
    app = create_app(
        connections,
        ai_settings=service,
        enforce_local_security=True,
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.put(
            "/api/settings/ai",
            headers={"Origin": "http://evil.example"},
            json={"model": None, "responseMode": "balanced", "outputContinuation": "2", "responseDelivery": "stream", "logFullPrompts": False},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_runtime_composes_ai_settings_from_provider_runtime_app_paths(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    runtime = create_system_runtime(app_paths=paths)

    assert runtime.ai_settings.__class__.__name__ == "AiSettingsService"
    assert not paths.home.exists()

    run(runtime.aclose())


def test_system_app_uses_one_injected_data_root_for_ai_settings(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    app = create_system_app(app_paths=paths)

    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/settings/ai")
        assert response.status_code == 200
        assert response.json() == {"model": None, "responseMode": "default", "outputContinuation": "2", "responseDelivery": "stream", "logFullPrompts": False}

    assert paths.backend_logs_dir.is_dir()
    assert not paths.config_dir.exists()
    assert not paths.data_dir.exists()
