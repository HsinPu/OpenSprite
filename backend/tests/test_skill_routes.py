"""Strict Skills API regression checks."""
from fastapi.testclient import TestClient
from opensprite_backend.app import create_app
from test_skills import setup, CONTENT


def client_for(tmp_path):
    app = create_app()
    app.state.skills = setup(tmp_path)
    return TestClient(app)


def test_create_approve_read_and_archive(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/skills/settings").json() == {"enabled": True, "revision": 0}
        response = client.post("/api/skills", json={"scope": "global", "content": CONTENT, "expectedRevision": 0})
        assert response.status_code == 200
        item = response.json()["skill"]
        assert not item["effective"]
        assert client.put(f'/api/skills/{item["id"]}/enabled', json={"enabled": True, "confirmedHash": item["contentHash"], "expectedRevision": 1}).status_code == 200
        assert client.get("/api/skills?scope=global").json()["skills"][0]["effective"]
        assert client.delete(f'/api/skills/{item["id"]}?expectedRevision=2').status_code == 200
        assert client.get("/api/skills?scope=global").json()["skills"] == []


def test_reject_duplicate_unknown_and_invalid_fields(tmp_path):
    with client_for(tmp_path) as client:
        for content in ['{"enabled":true,"enabled":false,"expectedRevision":0}',
                        '{"enabled":true,"expectedRevision":0,"extra":1}',
                        '{"enabled":true,"expectedRevision":true}']:
            assert client.put("/api/skills/settings", content=content).status_code == 400
        for suffix in ["?scope=global&scope=workspace", "?scope=workspace", "?scope=global&extra=x"]:
            assert client.get("/api/skills" + suffix).status_code == 400


def test_revision_and_changed_content(tmp_path):
    with client_for(tmp_path) as client:
        assert client.put("/api/skills/settings", json={"enabled": False, "expectedRevision": 5}).status_code == 409
        item = client.post("/api/skills", json={"scope": "global", "content": CONTENT, "expectedRevision": 0}).json()["skill"]
        assert client.put(f'/api/skills/{item["id"]}/enabled', json={"enabled": True, "confirmedHash": "0" * 64, "expectedRevision": 1}).status_code == 409


def test_skills_routes_require_authentication(tmp_path):
    from test_authentication import authentication
    auth, _ = authentication(tmp_path)
    app = create_app(local_authentication=auth, enforce_authentication=True)
    with TestClient(app) as client:
        for method, path in [("GET", "/settings"), ("PUT", "/settings"), ("GET", "?scope=global"), ("POST", ""), ("POST", "/scan"), ("GET", "/11111111-1111-4111-8111-111111111111"), ("PUT", "/11111111-1111-4111-8111-111111111111"), ("DELETE", "/11111111-1111-4111-8111-111111111111?expectedRevision=0"), ("PUT", "/11111111-1111-4111-8111-111111111111/enabled"), ("PUT", "/11111111-1111-4111-8111-111111111111/workspace-override")]:
            assert client.request(method, "/api/skills" + path).status_code == 401
