"""Strict HTTP inspection and cancellation contracts for child executions."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.application import AgentChatError, ChatErrorCode
from opensprite_backend.custom_agents.models import AgentError
from opensprite_backend.custom_agents.child_repository import ChildExecution


PARENT_ID = str(uuid4())


def child(parent_id: str = PARENT_ID) -> ChildExecution:
    return ChildExecution(
        id=str(uuid4()),
        parent_run_id=parent_id,
        spawn_call_id="call-1",
        request_hash="a" * 64,
        agent_id=str(uuid4()),
        agent_name="reviewer",
        agent_revision=2,
        definition_hash="b" * 64,
        provider_id="openrouter",
        model_id="openrouter/auto",
        status="completed",
        result_text="x" * 5000,
        error_code=None,
        created_at=datetime(2026, 9, 9, 1, 2, 3, tzinfo=UTC).isoformat(),
        started_at=datetime(2026, 9, 9, 1, 2, 4, tzinfo=UTC).isoformat(),
        finished_at=datetime(2026, 9, 9, 1, 2, 5, tzinfo=UTC).isoformat(),
    )


class FakeChat:
    def __init__(self, parent_id: str = PARENT_ID, *, exists: bool = True) -> None:
        self.parent_id = parent_id
        self.exists = exists

    async def get_run(self, run_id: str):
        if not self.exists or run_id != self.parent_id:
            raise AgentChatError(ChatErrorCode.NOT_FOUND)
        return SimpleNamespace(id=run_id)


class FakeStore:
    def __init__(self, children: tuple[ChildExecution, ...]) -> None:
        self.children = list(children)

    def list(self, parent_id: str):
        return tuple(child for child in self.children if child.parent_run_id == parent_id)

    def get(self, parent_id: str, child_id: str):
        for item in self.children:
            if item.parent_run_id == parent_id and item.id == child_id:
                return item
        raise AgentError("not_found")


class FakeDelegation:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.calls: list[tuple[str, str]] = []

    async def cancel_child(self, parent_id: str, child_id: str):
        self.calls.append((parent_id, child_id))
        item = self.store.get(parent_id, child_id)
        cancelled = replace(item, status="cancelled", finished_at=item.finished_at)
        self.store.children = [cancelled if child.id == item.id else child for child in self.store.children]
        return cancelled


def client_for(
    children: tuple[ChildExecution, ...] = (),
    *,
    exists: bool = True,
):
    app = create_app()
    store = FakeStore(children)
    delegation = FakeDelegation(store)
    app.state.agent_chat = FakeChat(exists=exists)
    app.state.child_executions = store
    app.state.delegation = delegation
    return TestClient(app), store, delegation


def test_list_returns_strict_summaries_and_parent_empty_is_valid():
    item = child()
    client, _, _ = client_for((item,))
    with client:
        response = client.get(f"/api/runs/{PARENT_ID}/agents")
    assert response.status_code == 200
    payload = response.json()
    assert list(payload) == ["items"]
    assert payload["items"][0] == {
        "id": item.id,
        "parentRunId": PARENT_ID,
        "agentId": item.agent_id,
        "name": "reviewer",
        "revision": 2,
        "providerId": "openrouter",
        "modelId": "openrouter/auto",
        "status": "completed",
        "errorCode": None,
        "createdAt": "2026-09-09T01:02:03Z",
        "startedAt": "2026-09-09T01:02:04Z",
        "finishedAt": "2026-09-09T01:02:05Z",
    }

    empty_client, _, _ = client_for((), exists=True)
    with empty_client:
        assert empty_client.get(f"/api/runs/{PARENT_ID}/agents").json() == {"items": []}


def test_result_is_owned_and_paged_at_4000_characters():
    item = child()
    client, _, _ = client_for((item,))
    with client:
        response = client.get(f"/api/runs/{PARENT_ID}/agents/{item.id}?offset=1000")
    assert response.status_code == 200
    assert response.json() == {
        "childId": item.id,
        "status": "completed",
        "error": None,
        "text": "x" * 4000,
        "nextOffset": None,
    }

    other = child(str(uuid4()))
    with client:
        missing = client.get(f"/api/runs/{other.parent_run_id}/agents/{item.id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_cancel_uses_coordinator_and_is_strictly_bodyless():
    item = child()
    client, _, delegation = client_for((item,))
    with client:
        response = client.post(f"/api/runs/{PARENT_ID}/agents/{item.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert delegation.calls == [(PARENT_ID, item.id)]

    with client:
        assert client.post(
            f"/api/runs/{PARENT_ID}/agents/{item.id}/cancel?x=1"
        ).json()["error"]["code"] == "invalid_request"
        assert client.post(
            f"/api/runs/{PARENT_ID}/agents/{item.id}/cancel",
            json={},
        ).json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize(
    "path",
    [
        "/api/runs/not-a-uuid/agents",
        f"/api/runs/{PARENT_ID}/agents?offset=0",
        f"/api/runs/{PARENT_ID}/agents?x=1",
        f"/api/runs/{PARENT_ID}/agents/{uuid4()}?offset=0&offset=1",
        f"/api/runs/{PARENT_ID}/agents/{uuid4()}?offset=-1",
        f"/api/runs/{PARENT_ID}/agents/{uuid4()}?offset=true",
    ],
)
def test_get_rejects_unknown_duplicate_and_invalid_query(path):
    client, _, _ = client_for(())
    with client:
        response = client.get(path)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_list_requires_existing_parent_and_authentication_boundary_is_unchanged():
    client, _, _ = client_for((), exists=False)
    with client:
        response = client.get(f"/api/runs/{PARENT_ID}/agents")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_subagent_contract_documents_only_the_three_inspection_operations():
    contract = json.loads(
        (Path(__file__).parents[2] / "contracts" / "subagents.openapi.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["openapi"] == "3.1.0"
    assert set(contract["paths"]) == {
        "/api/runs/{parent_id}/agents",
        "/api/runs/{parent_id}/agents/{child_id}",
        "/api/runs/{parent_id}/agents/{child_id}/cancel",
    }
    assert contract["paths"]["/api/runs/{parent_id}/agents"]["get"]["operationId"] == "listSubagents"
    assert contract["paths"]["/api/runs/{parent_id}/agents/{child_id}"]["get"]["operationId"] == "getSubagentResult"
    assert contract["paths"]["/api/runs/{parent_id}/agents/{child_id}/cancel"]["post"]["operationId"] == "cancelSubagent"
    for name in ("SubagentSummary", "SubagentList", "SubagentResult", "AgentErrorResponse"):
        assert contract["components"]["schemas"][name]["additionalProperties"] is False
