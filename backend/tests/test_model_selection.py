"""Tests for strict, local-only persisted model selection."""

from __future__ import annotations

from asyncio import run
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.model_selection import (
    JsonModelSelectionStore,
    ModelSelectionService,
    SettingsStoreError,
    create_model_selection_service,
)
from opensprite_backend.models import (
    ErrorCode,
    ModelSelection,
    PutModelSelectionRequest,
    ProviderListResponse,
    ProviderStatus,
    ProviderSummary,
)
from opensprite_backend.provider_connections import ProviderConnectionError
from opensprite_backend.runtime import create_system_app, create_system_runtime


def selection() -> ModelSelection:
    return ModelSelection(providerId="openai", modelId="gpt-5.6")


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


def test_store_round_trip_lazy_read_and_clear(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    store = JsonModelSelectionStore(paths.settings_file)

    assert store.get() is None
    assert not paths.home.exists()
    store.set(selection())

    assert store.get() == selection()
    assert json.loads(paths.settings_file.read_text(encoding="utf-8")) == {
        "version": 1,
        "defaultModel": {"providerId": "openai", "modelId": "gpt-5.6"},
    }
    assert sorted(path.relative_to(paths.home).as_posix() for path in paths.home.rglob("*")) == [
        "config",
        "config/settings.json",
    ]

    store.set(None)
    assert not paths.settings_file.exists()


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":1,"defaultModel":{"providerId":"openai","modelId":"gpt-5.6"},"extra":true}',
        '{"version":1,"version":1,"defaultModel":{"providerId":"openai","modelId":"gpt-5.6"}}',
        '{"version":1,"defaultModel":{"providerId":"openai","modelId":"gpt-5.6","extra":true}}',
        '{"version":2,"defaultModel":{"providerId":"openai","modelId":"gpt-5.6"}}',
        '{"version":1,"defaultModel":{"providerId":"other","modelId":"gpt-5.6"}}',
        '{"version":1,"defaultModel":{"providerId":"openai","modelId":"   "}}',
    ],
)
def test_store_rejects_malformed_or_noncanonical_json(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(SettingsStoreError) as raised:
        JsonModelSelectionStore(path).get()

    assert str(raised.value) == "Model selection settings are unavailable."
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_store_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(SettingsStoreError):
        JsonModelSelectionStore(path).get()


def test_atomic_failure_cleans_temp_and_preserves_old_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config" / "settings.json"
    store = JsonModelSelectionStore(path)
    store.set(selection())
    before = path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("private replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(SettingsStoreError) as raised:
        store.set(ModelSelection(providerId="anthropic", modelId="claude"))

    assert str(raised.value) == "Model selection settings are unavailable."
    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_service_checks_connection_only_for_non_null_selection(
    tmp_path: Path,
) -> None:
    connections = RecordingConnections(connected=False)
    service = ModelSelectionService(
        JsonModelSelectionStore(tmp_path / "settings.json"),
        connections,
    )

    with pytest.raises(ProviderConnectionError) as raised:
        run(service.put(PutModelSelectionRequest(selection=selection())))
    assert raised.value.code is ErrorCode.NOT_CONNECTED
    assert connections.list_calls == 1

    response = run(service.put(PutModelSelectionRequest(selection=None)))
    assert response.selection is None
    assert connections.list_calls == 1


def test_api_routes_return_selection_and_map_errors(tmp_path: Path) -> None:
    connections = RecordingConnections()
    service = ModelSelectionService(
        JsonModelSelectionStore(tmp_path / "settings.json"),
        connections,
    )
    with TestClient(create_app(connections, model_selection=service)) as client:
        initial = client.get("/api/settings/model")
        saved = client.put(
            "/api/settings/model",
            json={"selection": {"providerId": "openai", "modelId": "gpt-5.6"}},
        )
        invalid = client.put(
            "/api/settings/model",
            json={"selection": {"providerId": "openai", "modelId": "   "}},
        )

    assert initial.json() == {"selection": None}
    assert saved.status_code == 200
    assert saved.json() == {
        "selection": {"providerId": "openai", "modelId": "gpt-5.6"}
    }
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_request"


def test_same_origin_protection_applies_to_selection_put(tmp_path: Path) -> None:
    connections = RecordingConnections()
    service = ModelSelectionService(
        JsonModelSelectionStore(tmp_path / "settings.json"),
        connections,
    )
    app = create_app(
        connections,
        model_selection=service,
        enforce_local_security=True,
    )
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.put(
            "/api/settings/model",
            headers={"Origin": "http://evil.example"},
            json={"selection": None},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_runtime_composes_selection_from_provider_runtime_app_paths(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    runtime = create_system_runtime(app_paths=paths)

    assert runtime.model_selection.__class__.__name__ == "ModelSelectionService"
    assert not paths.home.exists()

    run(runtime.aclose())


def test_system_app_uses_one_injected_data_root_for_model_selection(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    app = create_system_app(app_paths=paths)

    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/settings/model")
        assert response.status_code == 200
        assert response.json() == {"selection": None}

    assert not paths.home.exists()
