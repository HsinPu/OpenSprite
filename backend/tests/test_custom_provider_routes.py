from fastapi.testclient import TestClient
import httpx
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import pytest
from starlette.requests import Request

from opensprite_backend.api.custom_provider_routes import mutation_body
from opensprite_backend.api.custom_provider_models import ProviderCreateRequest
from opensprite_backend.providers.catalog_store import CatalogError

from opensprite_backend.app import create_app
from opensprite_backend.credentials.encrypted_json_store import EncryptedJsonCredentialStore
from opensprite_backend.providers.catalog_store import JsonProviderCatalog
from opensprite_backend.providers.catalog_transaction import ProviderCatalogTransaction
from opensprite_backend.providers.custom_service import CustomProviderService
from opensprite_backend.providers.mutations import ProviderMutations
from opensprite_backend.workspaces import WorkspaceMutationGate


def client_for(tmp_path):
    app = create_app()
    app.state.custom_providers = CustomProviderService(ProviderCatalogTransaction(
        JsonProviderCatalog(tmp_path / "providers.json"),
        EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key"),
        tmp_path / "transaction.json",
    ))
    app.state.provider_mutations = ProviderMutations(app.state.custom_providers,
        WorkspaceMutationGate(), SimpleNamespace(provider_usage=lambda *_: (0, 0)),
        SimpleNamespace(provider_in_use=lambda _: False), SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(model=None))),
        SimpleNamespace(references_provider=lambda *_: False))
    return TestClient(app)


def test_create_read_and_revision_conflict(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/providers/catalog").json() == {"revision": 0, "providers": [], "nextCursor": None}
        payload = dict(name="Private", baseUrl="https://example.com/v1", protocol="openai_chat_completions", authMode="bearer", apiKey="private-key", expectedRevision=0)
        result = client.post("/api/providers", json=payload)
        assert result.status_code == 201
        assert "private-key" not in result.text
        provider_id = result.json()["id"]
        assert client.get("/api/providers/catalog").json() == {"revision": 1, "providers": [result.json()], "nextCursor": None}
        assert client.get(f"/api/providers/{provider_id}").json()["name"] == "Private"
        assert client.post("/api/providers", json=payload).status_code == 409


def test_duplicate_json_rejected_without_writing(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/api/providers", content='{"name":"a","name":"b"}', headers={"Content-Type":"application/json"})
        assert response.status_code == 400
        assert not (tmp_path / "providers.json").exists()


def test_tool_policy_defaults_and_partial_update_preservation(tmp_path):
    with client_for(tmp_path) as client:
        fields = dict(name="Tools", baseUrl="https://example.com/v1", protocol="openai_chat_completions", authMode="none")
        created = client.post("/api/providers", json={**fields, "expectedRevision": 0}).json()
        assert created["tools_enabled"] and created["non_streaming_tools"]
        url = f"/api/providers/{created['id']}"
        response = client.put(url, json={**fields, "expectedRevision": 1, "toolsEnabled": False, "nonStreamingTools": False})
        assert response.status_code == 200
        response = client.put(url, json={**fields, "expectedRevision": 2})
        assert response.status_code == 200
        assert not response.json()["tools_enabled"] and not response.json()["non_streaming_tools"]


def test_mutation_stream_stops_at_size_limit():
    receive = AsyncMock(side_effect=[
        {"type": "http.request", "body": b" " * 65536, "more_body": True},
        {"type": "http.request", "body": b" ", "more_body": True},
        AssertionError("Oversized request must not be consumed further"),
    ])
    request = Request({"type": "http", "method": "POST", "path": "/api/providers", "headers": []}, receive)
    with pytest.raises(CatalogError) as raised:
        asyncio.run(mutation_body(request, ProviderCreateRequest))
    assert raised.value.code == "invalid_request"
    assert receive.await_count == 2


def test_catalog_pagination_is_revision_bound_and_strict(tmp_path):
    with client_for(tmp_path) as client:
        for revision in range(3):
            response = client.post("/api/providers", json=dict(name=f"Local {revision}",
                baseUrl="https://example.com/v1", protocol="openai_chat_completions", authMode="none", expectedRevision=revision))
            assert response.status_code == 201
        first = client.get("/api/providers/catalog?limit=2").json()
        assert len(first["providers"]) == 2
        assert first["nextCursor"] == "3:2"
        last = client.get("/api/providers/catalog?cursor=3:2&limit=2").json()
        assert len(last["providers"]) == 1 and last["nextCursor"] is None
        assert len({item["id"] for item in first["providers"] + last["providers"]}) == 3
        for query in ("limit=0", "limit=101", "limit=2&limit=3", "unknown=1", "cursor=garbage", "cursor=3:3"):
            assert client.get(f"/api/providers/catalog?{query}").status_code == 400
        assert client.get("/api/providers/catalog?cursor=2:1").status_code == 409


def test_custom_model_discovery_http_route(tmp_path):
    with client_for(tmp_path) as client:
        client.app.state.provider_http_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data":[{"id":"custom-model"}]})))
        result = client.post("/api/providers", json=dict(name="Local", baseUrl="https://example.com/v1", protocol="openai_chat_completions", authMode="none", expectedRevision=0))
        identifier = result.json()["id"]
        refreshed = client.post(f"/api/providers/{identifier}/models/refresh", json={"expectedRevision":1})
        assert refreshed.status_code == 200
        assert refreshed.json()["models"][0]["model_id"] == "custom-model"
        assert client.get(f"/api/providers/{identifier}/models").json() == {**refreshed.json(), "nextCursor": None}


def test_manual_model_without_discovery(tmp_path):
    with client_for(tmp_path) as client:
        result = client.post("/api/providers", json=dict(name="Local", baseUrl="https://example.com/v1", protocol="openai_chat_completions", authMode="none", expectedRevision=0))
        url = f"/api/providers/{result.json()['id']}/models"
        payload = dict(modelId="local-model", name="Local model", contextLimit=16384,
            outputLimit=4096, tools=True, expectedRevision=1)
        created = client.post(url, json=payload)
        assert created.status_code == 201
        model = created.json()["models"][0]
        assert model["source"] == "manual"
        assert model["tools"] is True
        assert client.post(url, json=payload).status_code == 409
        payload["expectedRevision"] = 2
        assert client.post(url, json=payload).json()["error"]["code"] == "duplicate_model"
        assert client.post(url, json={**payload, "unexpected": True}).status_code == 400
        assert client.get(url).json() == {**created.json(), "nextCursor": None}


def test_model_pages_reject_stale_or_invalid_queries(tmp_path):
    with client_for(tmp_path) as client:
        identifier = client.post("/api/providers", json=dict(name="Local", baseUrl="https://example.com/v1",
            protocol="openai_chat_completions", authMode="none", expectedRevision=0)).json()["id"]
        url = f"/api/providers/{identifier}/models"
        for revision in range(1, 4):
            assert client.post(url, json=dict(modelId=f"model-{revision}", name="Model", contextLimit=4096,
                outputLimit=1024, tools=False, expectedRevision=revision)).status_code == 201
        first = client.get(url + "?limit=2").json()
        assert first["nextCursor"] == "4:2"
        last = client.get(url + "?cursor=4:2").json()
        assert len(last["models"]) == 1 and last["nextCursor"] is None
        for query in ("limit=0", "limit=101", "limit=1&limit=2", "cursor=x", "cursor=4:3", "unknown=x"):
            assert client.get(url + "?" + query).status_code == 400
        assert client.get(url + "?cursor=3:1").status_code == 409


def test_guarded_update_and_delete(tmp_path):
    with client_for(tmp_path) as client:
        fields = dict(name="Local", baseUrl="https://example.com/v1", protocol="openai_chat_completions", authMode="none", expectedRevision=0)
        created = client.post("/api/providers", json=fields).json()
        url = f"/api/providers/{created['id']}"
        updated = client.put(url, json={**fields, "name": "Renamed", "expectedRevision": 1})
        assert updated.status_code == 200
        assert updated.json()["name"] == "Renamed"
        guard = client.app.state.provider_mutations
        guard.run_manager.provider_in_use = lambda _: True
        assert client.put(url, json={**fields, "expectedRevision": 2}).json()["error"]["code"] == "provider_busy"
        assert client.delete(url, params={"expectedRevision": 2}).status_code == 409
        guard.run_manager.provider_in_use = lambda _: False
        guard.repository.provider_usage = lambda *_: (0, 1)
        assert client.delete(url, params={"expectedRevision": 2}).json()["error"]["code"] == "provider_in_use"
        guard.repository.provider_usage = lambda *_: (0, 0)
        for query in ("", "?expectedRevision=0", "?expectedRevision=2&extra=1", "?expectedRevision=2&expectedRevision=2"):
            assert client.delete(url + query).status_code == 400
        assert client.delete(url, params={"expectedRevision": 2}).json() == {"deleted": True}
        assert client.get(url).status_code == 404


def test_model_mutations_reject_selected_model_removal(tmp_path):
    with client_for(tmp_path) as client:
        created = client.post("/api/providers", json=dict(name="Local", baseUrl="https://example.com/v1",
            protocol="openai_chat_completions", authMode="none", expectedRevision=0)).json()
        provider_id = created["id"]
        url = f"/api/providers/{provider_id}/models"
        fields = dict(modelId="local", name="Local", contextLimit=8192, outputLimit=2048, tools=False, expectedRevision=1)
        model = client.post(url, json=fields).json()["models"][0]
        model_url = f"{url}/{model['key']}"
        guard = client.app.state.provider_mutations
        guard.ai_settings.get.return_value = SimpleNamespace(model=SimpleNamespace(provider_id=provider_id, model_id="local"))
        assert client.delete(model_url, params={"expectedRevision": 2}).json()["error"]["code"] == "provider_in_use"
        assert client.put(model_url, json={**fields, "modelId": "changed", "expectedRevision": 2}).status_code == 409
        edited = client.put(model_url, json={**fields, "name": "Display name", "expectedRevision": 2})
        assert edited.status_code == 200
        assert edited.json()["models"][0]["key"] == model["key"]
        guard.ai_settings.get.return_value = SimpleNamespace(model=None)
        assert client.delete(model_url, params={"expectedRevision": 3}).json() == {"revision": 4, "models": []}


def test_discovery_cannot_remove_referenced_models_or_change_live_runs(tmp_path):
    with client_for(tmp_path) as client:
        ids = ["remote"]
        client.app.state.provider_http_client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": [{"id": value} for value in ids]})))
        created = client.post("/api/providers", json=dict(name="Local", baseUrl="https://example.com/v1",
            protocol="openai_chat_completions", authMode="none", expectedRevision=0)).json()
        identifier = created["id"]
        url = f"/api/providers/{identifier}/models"
        original = client.post(url + "/refresh", json={"expectedRevision": 1}).json()
        guard = client.app.state.provider_mutations
        guard.ai_settings.get.return_value = SimpleNamespace(model=SimpleNamespace(provider_id=identifier, model_id="remote"))
        ids.clear()
        rejected = client.post(url + "/refresh", json={"expectedRevision": 2})
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "provider_in_use"
        assert client.get(url).json() == {**original, "nextCursor": None}
        guard.ai_settings.get.return_value = SimpleNamespace(model=None)
        guard.run_manager.provider_in_use = lambda _: True
        assert client.post(url + "/refresh", json={"expectedRevision": 2}).json()["error"]["code"] == "provider_busy"
        assert client.get(url).json() == {**original, "nextCursor": None}
        guard.run_manager.provider_in_use = lambda _: False
        assert client.post(url + "/refresh", json={"expectedRevision": 2}).json() == {"revision": 3, "models": []}
