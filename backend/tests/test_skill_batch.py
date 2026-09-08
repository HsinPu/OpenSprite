"""Batch policies, strict HTTP boundaries and crash-safe archive recovery."""
import json
from pathlib import Path

import pytest

from opensprite_backend.skills.models import SkillError
from test_skills import CONTENT, WORKSPACE_ID, setup
from test_skill_routes import client_for


def add(service, name, scope="global"):
    return service.save(scope=scope, workspace_id=WORKSPACE_ID if scope == "workspace" else None,
                        content=CONTENT.replace("name: review", f"name: {name}"), expected=service.settings()["revision"])["skill"]


def batch(service, action, scope="global"):
    return service.batch(scope=scope, workspace_id=WORKSPACE_ID if scope == "workspace" else None,
                         action=action, expected=service.settings()["revision"])


def test_batch_enable_skips_invalid_and_preserves_master_and_other_scope(tmp_path):
    service = setup(tmp_path)
    good = add(service, "good")
    bad = add(service, "bad")
    local = add(service, "local", "workspace")
    batch(service, "disable")
    service.configure(expected=4, enabled=False)
    (service.paths.skills_dir / "bad/SKILL.md").write_text("invalid", encoding="utf-8")
    result = batch(service, "enable")
    assert result["completed"] == 1
    assert result["skipped"] == [{"id": bad["id"], "reason": "invalid_format"}]
    assert not result["failed"]
    assert service.get(good["id"])["skill"]["enabled"]
    assert service.get(local["id"])["skill"]["enabled"]
    assert not service.settings()["enabled"]
    assert not service.snapshot(WORKSPACE_ID).available


def test_batch_enable_name_conflicts_and_noop_revision(tmp_path):
    service = setup(tmp_path)
    add(service, "first"); add(service, "second")
    batch(service, "disable")
    (service.paths.skills_dir / "second/SKILL.md").write_text(CONTENT.replace("review", "FIRST"), encoding="utf-8")
    result = batch(service, "enable")
    assert result["completed"] == 0 and result["revision"] == 3
    assert {x["reason"] for x in result["skipped"]} == {"duplicate_name"}
    assert batch(service, "disable")["revision"] == 3


def test_batch_archive_isolates_scope_preserves_files_and_snapshots(tmp_path):
    service = setup(tmp_path)
    global_item = add(service, "review")
    local = add(service, "review", "workspace")
    frozen = service.snapshot(WORKSPACE_ID)
    assert batch(service, "disable", "workspace")["completed"] == 1
    assert not service.snapshot(WORKSPACE_ID).available
    assert batch(service, "archive", "workspace")["completed"] == 1
    assert frozen.available[0].id == local["id"]
    assert service.snapshot(WORKSPACE_ID).available[0].id == global_item["id"]
    assert next(service.paths.skills_archive_dir.glob("*/SKILL.md")).read_text() == CONTENT
    assert service.list("global")["skills"]
    assert not service.list("workspace", WORKSPACE_ID)["skills"]


def test_archive_missing_files_and_preflight_failure_remain_reported(tmp_path, monkeypatch):
    service = setup(tmp_path)
    good = add(service, "good"); bad = add(service, "bad")
    (service.paths.skills_dir / "good/SKILL.md").unlink()
    original = service._path
    def checked(item):
        if item.id == bad["id"]:
            raise SkillError("unsafe_path")
        return original(item)
    monkeypatch.setattr(service, "_path", checked)
    result = batch(service, "archive")
    assert result["completed"] == 1
    assert result["failed"] == [{"id": bad["id"], "reason": "unsafe_path"}]
    assert [x["id"] for x in service.list("global")["skills"]] == [bad["id"]]


def test_partial_archive_recovers_without_losing_catalog_or_files(tmp_path, monkeypatch):
    service = setup(tmp_path)
    add(service, "first"); add(service, "second")
    original = Path.rename
    def fail_second(path, target):
        if path.name == "second":
            raise OSError("injected")
        return original(path, target)
    monkeypatch.setattr(Path, "rename", fail_second)
    with pytest.raises(SkillError, match="store_unavailable"):
        batch(service, "archive")
    assert len(json.loads(service.paths.skills_settings_file.read_text())["skills"]) == 2
    assert service.paths.skills_transaction_file.exists()
    monkeypatch.setattr(Path, "rename", original)
    from opensprite_backend.skills.service import SkillsService
    restarted = SkillsService(service.paths, service.workspaces)
    assert restarted.list("global")["skills"] == []
    assert len(list(service.paths.skills_archive_dir.glob("*/SKILL.md"))) == 2
    assert not service.paths.skills_transaction_file.exists()


def test_toggle_write_failure_is_atomic(tmp_path, monkeypatch):
    service = setup(tmp_path); add(service, "first")
    before = service.paths.skills_settings_file.read_bytes()
    import opensprite_backend.skills.service as module
    monkeypatch.setattr(module, "atomic_write", lambda *args: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(SkillError):
        batch(service, "disable")
    assert service.paths.skills_settings_file.read_bytes() == before


def test_strict_batch_http_and_revision(tmp_path):
    with client_for(tmp_path) as client:
        base = {"scope": "global", "workspaceId": None, "action": "disable", "expectedRevision": 0}
        assert client.post("/api/skills/batch", json=base).json()["completed"] == 0
        for patch in [{"extra": True}, {"action": "delete"}, {"scope": "workspace"}, {"workspaceId": WORKSPACE_ID}, {"expectedRevision": True}]:
            assert client.post("/api/skills/batch", json={**base, **patch}).status_code == 400
        assert client.post("/api/skills/batch", content='{"scope":"global","scope":"global"}').status_code == 400
        assert client.post("/api/skills/batch", json={**base, "expectedRevision": 99}).status_code == 409
        assert client.post("/api/skills/batch?extra=x", json=base).status_code == 400


def test_batch_requires_auth(tmp_path):
    from fastapi.testclient import TestClient
    from opensprite_backend.app import create_app
    from test_authentication import authentication
    auth, _ = authentication(tmp_path)
    with TestClient(create_app(local_authentication=auth, enforce_authentication=True)) as client:
        assert client.post("/api/skills/batch", json={}).status_code == 401
