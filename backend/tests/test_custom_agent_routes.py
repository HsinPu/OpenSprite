"""Strict routing and authentication independently of filesystem behavior."""

import asyncio
from contextlib import asynccontextmanager
from threading import Event
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.api.custom_agent_routes import execute
from opensprite_backend.custom_agents.models import AgentError


class Gate:
    @asynccontextmanager
    async def hold(self):
        yield


class FakeAgents:
    def __init__(self):
        self.workspaces = SimpleNamespace(mutation_gate=Gate())
        self.calls = []

    def settings(self):
        return {"enabled": True, "revision": 0}

    def set_settings(self, enabled, expected):
        if expected != 0:
            raise AgentError("revision_conflict")
        return {"enabled": enabled, "revision": 1}

    def list_agents(self, scope, workspace_id, cursor, limit):
        self.calls.append((scope, workspace_id, cursor, limit))
        return {"revision": 0, "items": [], "nextCursor": None}

    def remove(self, identifier, expected):
        self.calls.append((identifier, expected))


def client_for():
    app = create_app()
    app.state.custom_agents = FakeAgents()
    return TestClient(app)


def test_settings_and_list():
    with client_for() as client:
        assert client.get("/api/agents/settings").json() == {"enabled": True, "revision": 0}
        assert client.put("/api/agents/settings", json={"enabled": False, "expectedRevision": 0}).json() == {"enabled": False, "revision": 1}
        assert client.get("/api/agents?scope=global&limit=30").json() == {"revision": 0, "items": [], "nextCursor": None}
        assert client.app.state.custom_agents.calls == [("global", None, None, 30)]


@pytest.mark.parametrize("raw", [
    '{"enabled":true,"enabled":false,"expectedRevision":0}',
    '{"enabled":true,"expectedRevision":0,"extra":1}',
    '{"enabled":true,"expectedRevision":true}',
    '{"enabled":true}',
    '{"enabled":1,"expectedRevision":0}',
    '[]',
])
def test_strict_body(raw):
    with client_for() as client:
        result = client.put("/api/agents/settings", content=raw, headers={"Content-Type": "application/json"})
        assert result.status_code == 400
        assert result.json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("suffix", [
    "", "?scope=global&scope=workspace", "?scope=workspace", "?scope=global&extra=x",
    "?scope=global&limit=0", "?scope=global&limit=101", "?scope=global&limit=true",
    "?scope=global&workspaceId=00000000-0000-4000-8000-000000000000",
    "?scope=workspace&workspaceId=bad", "?scope=global&cursor=",
])
def test_strict_list_query(suffix):
    with client_for() as client:
        assert client.get("/api/agents" + suffix).status_code == 400


@pytest.mark.parametrize("suffix", ["", "?expectedRevision=0&expectedRevision=0", "?expectedRevision=0&extra=x", "?expectedRevision=-1", "?expectedRevision=1.0", "?expectedRevision=true"])
def test_strict_delete_query(suffix):
    with client_for() as client:
        assert client.delete("/api/agents/00000000-0000-4000-8000-000000000001" + suffix).status_code == 400


def test_delete_204_and_revision_conflict():
    with client_for() as client:
        assert client.delete("/api/agents/00000000-0000-4000-8000-000000000001?expectedRevision=0").status_code == 204
        response = client.put("/api/agents/settings", json={"enabled": True, "expectedRevision": 9})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "revision_conflict"


def test_missing_service_fails_closed():
    with TestClient(create_app()) as client:
        assert client.get("/api/agents/settings").status_code == 503


def test_internal_response_error_does_not_log_definition(caplog):
    app = create_app()
    manager = FakeAgents()
    manager.settings = lambda: {"enabled": True, "revision": 0, "content": "PRIVATE_AGENT_INSTRUCTIONS"}
    app.state.custom_agents = manager
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/agents/settings")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "PRIVATE_AGENT_INSTRUCTIONS" not in caplog.text
    assert "PRIVATE_AGENT_INSTRUCTIONS" not in response.text


def test_routes_require_authentication(tmp_path):
    from test_authentication import authentication

    auth, _ = authentication(tmp_path)
    app = create_app(local_authentication=auth, enforce_authentication=True)
    with TestClient(app) as client:
        for method, path in [("GET", "/settings"), ("PUT", "/settings"), ("GET", "?scope=global"), ("POST", ""), ("POST", "/scan"), ("POST", "/batch"), ("GET", "/00000000-0000-4000-8000-000000000001"), ("PUT", "/00000000-0000-4000-8000-000000000001"), ("DELETE", "/00000000-0000-4000-8000-000000000001?expectedRevision=0"), ("PUT", "/00000000-0000-4000-8000-000000000001/enabled")]:
            result = client.request(method, "/api/agents" + path)
            assert result.status_code == 401
            assert result.json()["error"]["code"] == "authentication_required"


def test_cancelled_request_waits_for_worker_to_stop():
    async def scenario():
        started, release, finished = Event(), Event(), Event()

        def worker():
            started.set()
            assert release.wait(5)
            finished.set()

        task = asyncio.create_task(execute(worker))
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(scenario())


def test_openapi_document_matches_runtime_agents_routes():
    import json
    from pathlib import Path

    contract = json.loads((Path(__file__).parents[2] / "contracts" / "custom-agents.openapi.json").read_text(encoding="utf-8"))
    generated = create_app().openapi()
    assert contract["paths"] == {key: value for key, value in generated["paths"].items() if key.startswith("/api/agents")}
    for name, definition in contract["components"]["schemas"].items():
        assert definition == generated["components"]["schemas"][name]
