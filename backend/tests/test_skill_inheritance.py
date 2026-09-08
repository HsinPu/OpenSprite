"""Workspace precedence is resolved before availability, without global fallback."""
import json

import pytest

from opensprite_backend.skills.models import SkillError
from test_skills import CONTENT, WORKSPACE_ID, setup


def add(service, scope, name="review"):
    return service.save(scope=scope, workspace_id=WORKSPACE_ID if scope == "workspace" else None,
                        content=CONTENT.replace("name: review", f"name: {name}"),
                        expected=service.settings()["revision"])["skill"]


@pytest.mark.parametrize("failure", ["disabled", "missing", "invalid", "workspace_unavailable"])
def test_workspace_registration_shadows_even_when_unavailable(tmp_path, failure, monkeypatch):
    service = setup(tmp_path)
    global_item = add(service, "global")
    local = add(service, "workspace", "REVIEW")
    frozen = service.snapshot(WORKSPACE_ID)
    assert [x.id for x in frozen.available] == [local["id"]]
    path = service.paths.managed_workspaces_dir / "project/skills/REVIEW/SKILL.md"
    if failure == "disabled":
        service.configure(expected=2, identifier=local["id"], enabled=False)
    elif failure == "missing":
        path.unlink()
    elif failure == "invalid":
        path.write_text("bad", encoding="utf-8")
    else:
        monkeypatch.setattr(service.workspaces, "execution_context", lambda _: (_ for _ in ()).throw(ValueError()))
    assert not service.snapshot(WORKSPACE_ID).available
    view = service.list("global", WORKSPACE_ID)["skills"][0]
    assert view["reason"] == "shadowed_by_workspace"
    assert view["shadowedBySkillId"] == local["id"]
    assert not view["effective"]
    assert [x.id for x in service.snapshot("00000000-0000-4000-8000-000000000000").available] == [global_item["id"]]
    with pytest.raises(SkillError, match="skill_unavailable"):
        service.snapshot(WORKSPACE_ID, (global_item["id"],))
    assert frozen.get(local["id"]).body == "Check correctness."


def test_deletion_restores_global_and_global_toggle_does_not_control_local(tmp_path):
    service = setup(tmp_path)
    global_item = add(service, "global")
    local = add(service, "workspace")
    service.configure(expected=2, identifier=global_item["id"], enabled=False)
    assert service.snapshot(WORKSPACE_ID).available[0].id == local["id"]
    service.configure(expected=3, identifier=global_item["id"], enabled=True)
    service.delete(local["id"], 4)
    assert service.snapshot(WORKSPACE_ID).available[0].id == global_item["id"]


def test_external_name_resolution_nfc_casefold_and_conflicts(tmp_path):
    service = setup(tmp_path)
    global_item = add(service, "global", "Café")
    local = add(service, "workspace", "other")
    path = service.paths.managed_workspaces_dir / "project/skills/other/SKILL.md"
    path.write_text(CONTENT.replace("review", "CAFE\u0301"), encoding="utf-8")
    assert service.snapshot(WORKSPACE_ID).available[0].id == local["id"]
    assert service.list("global", WORKSPACE_ID)["skills"][0]["shadowedBySkillId"] == local["id"]
    other = add(service, "workspace", "third")
    (path.parent.parent / "third/SKILL.md").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    assert not service.snapshot(WORKSPACE_ID).available
    assert {v["state"] for v in service.list("workspace", WORKSPACE_ID)["skills"]} == {"duplicate_name"}
    with pytest.raises(SkillError):
        service.snapshot(WORKSPACE_ID, (global_item["id"], other["id"]))


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_override_migration_preserves_switches(tmp_path, version):
    service = setup(tmp_path)
    first = add(service, "global")
    second = add(service, "global", "other")
    service.configure(expected=2, identifier=second["id"], enabled=False)
    path = service.paths.skills_settings_file
    raw = json.loads(path.read_text())
    raw["version"] = version
    for item in raw["skills"]:
        item["disabledWorkspaces"] = [WORKSPACE_ID]
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert service.snapshot(WORKSPACE_ID).available[0].id == first["id"]
    saved = json.loads(path.read_text())
    assert saved["version"] == 3 and saved["revision"] == 4
    assert [s["enabled"] for s in saved["skills"]] == [True, False]
    assert all("disabledWorkspaces" not in s for s in saved["skills"])
    assert service.settings()["revision"] == 4


def test_v3_rejects_legacy_override_fields(tmp_path):
    service = setup(tmp_path)
    add(service, "global")
    path = service.paths.skills_settings_file
    raw = json.loads(path.read_text())
    raw["skills"][0]["disabledWorkspaces"] = []
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert not service.snapshot(WORKSPACE_ID).available
    with pytest.raises(SkillError, match="store_unavailable"):
        service.settings()


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("package", [False, True])
def test_legacy_journal_recovers_then_migrates(tmp_path, version, package):
    import base64
    from uuid import uuid4
    service = setup(tmp_path)
    record = {"id": str(uuid4()), "scope": "global", "workspaceId": None,
              "directoryName": "review", "name": "review", "description": "Review code",
              "revision": 1, "enabled": False, "confirmedHash": None, "disabledWorkspaces": [WORKSPACE_ID]}
    catalog = {"version": version, "revision": 1, "enabled": True, "skills": [record]}
    tx = {"version": 1, "catalog": catalog, "record": record, "content": CONTENT, "archive": None}
    if package:
        tx = {"version": 2, "catalog": catalog, "record": record,
              "files": [{"path": "SKILL.md", "data": base64.b64encode(CONTENT.encode()).decode()}]}
    journal = service.paths.skills_transaction_file
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(json.dumps(tx), encoding="utf-8")
    assert service.settings() == {"enabled": True, "revision": 2}
    assert service.get(record["id"])["skill"]["enabled"] is False
    assert not journal.exists()
    assert json.loads(service.paths.skills_settings_file.read_text())["version"] == 3
