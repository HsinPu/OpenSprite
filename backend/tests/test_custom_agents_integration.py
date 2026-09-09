"""Real filesystem and HTTP integration for agent management."""

import asyncio

from fastapi.testclient import TestClient

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import AppPaths
from opensprite_backend.custom_agents.service import CustomAgentsService
from test_workspaces import make_service, WORKSPACE_ID


CONTENT = 'name = "review"\ndescription = "Review code"\ndeveloper_instructions = "Return evidence"\n'


def setup(tmp_path):
    workspaces, data, _, _ = make_service(tmp_path)
    asyncio.run(workspaces.startup())
    asyncio.run(workspaces.create(name="project", expected_revision=0))
    service = CustomAgentsService(AppPaths(data), workspaces)
    app = create_app()
    app.state.custom_agents = service
    return TestClient(app), service


def test_create_update_disable_and_archive(tmp_path):
    client, service = setup(tmp_path)
    with client:
        response = client.post("/api/agents", json={"scope": "global", "content": CONTENT, "expectedRevision": 0})
        assert response.status_code == 201, response.text
        item = response.json()
        assert item["enabled"] and item["reason"] == "effective"
        identifier = item["id"]
        assert client.get(f"/api/agents/{identifier}").json()["content"] == CONTENT
        response = client.put(f"/api/agents/{identifier}", json={"content": CONTENT.replace("Review code", "Review changes"), "expectedRevision": 1})
        assert response.status_code == 200, response.text
        assert response.json()["description"] == "Review changes"
        response = client.put(f"/api/agents/{identifier}/enabled", json={"enabled": False, "expectedRevision": 2})
        assert response.status_code == 200, response.text
        assert not response.json()["enabled"]
        response = client.delete(f"/api/agents/{identifier}?expectedRevision=3")
        assert response.status_code == 204, response.text
        assert client.get("/api/agents?scope=global").json()["items"] == []
        assert any(service.paths.agents_archive_dir.rglob("*.toml"))


def test_workspace_shadowing_and_batch_do_not_mutate_inherited_global(tmp_path):
    client, service = setup(tmp_path)
    with client:
        global_item = client.post("/api/agents", json={"scope": "global", "content": CONTENT, "expectedRevision": 0}).json()
        response = client.post("/api/agents", json={"scope": "workspace", "workspaceId": WORKSPACE_ID, "content": CONTENT, "expectedRevision": 1})
        assert response.status_code == 201, response.text
        local_item = response.json()
        view = client.get(f"/api/agents?scope=workspace&workspaceId={WORKSPACE_ID}").json()
        inherited = next(item for item in view["items"] if item["id"] == global_item["id"])
        assert inherited["reason"] == "shadowed_by_workspace"
        assert inherited["shadowedByAgentId"] == local_item["id"]
        payload = {"scope": "workspace", "workspaceId": WORKSPACE_ID, "ids": [global_item["id"]], "action": "disable", "expectedRevision": 2}
        response = client.post("/api/agents/batch", json=payload)
        assert response.status_code == 400, response.text
        payload["ids"] = [local_item["id"]]
        response = client.post("/api/agents/batch", json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["affected"] == 1
        assert not service.snapshot(WORKSPACE_ID).available
        assert client.get(f'/api/agents/{global_item["id"]}').json()["enabled"]


def test_scan_creates_enabled_registration_and_revision_conflict(tmp_path):
    client, service = setup(tmp_path)
    service.paths.agents_dir.mkdir(parents=True)
    (service.paths.agents_dir / "review.toml").write_text(CONTENT, encoding="utf-8")
    with client:
        response = client.post("/api/agents/scan", json={"scope": "global", "expectedRevision": 0})
        assert response.status_code == 200, response.text
        assert response.json() == {"revision": 1, "added": 1}
        assert client.get("/api/agents?scope=global").json()["items"][0]["enabled"]
        assert client.put("/api/agents/settings", json={"enabled": False, "expectedRevision": 0}).status_code == 409
