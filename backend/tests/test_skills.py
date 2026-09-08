"""Skills approval, scoping and immutable content tests."""
from asyncio import run
import json
import pytest
from opensprite_backend.app_paths import AppPaths
from opensprite_backend.skills.format import parse
from opensprite_backend.skills.models import SkillError
from opensprite_backend.skills.service import SkillsService
from test_workspaces import make_service, WORKSPACE_ID

CONTENT = "---\nname: review\ndescription: Review code\n---\nCheck correctness."


def test_additional_metadata_and_long_description_round_trip(tmp_path):
    service = setup(tmp_path)
    description = "說明" * 1000
    content = f"---\nname: review\ndescription: {description}\nlicense: MIT\nmetadata:\n  author: tester\n---\nCheck correctness."
    item = service.save(scope="global", workspace_id=None, content=content, expected=0)["skill"]
    assert item["description"] == description
    assert service.get(item["id"])["skill"]["content"] == content


def setup(tmp_path):
    workspaces, data, _, _ = make_service(tmp_path)
    run(workspaces.startup())
    run(workspaces.create(name="project", expected_revision=0))
    return SkillsService(AppPaths(data), workspaces)


def test_approval_scope_and_frozen_snapshot(tmp_path):
    service = setup(tmp_path)
    created = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)
    item = created["skill"]
    assert service.snapshot(WORKSPACE_ID).available
    service.configure(expected=1, identifier=item["id"], enabled=True)
    snapshot = service.snapshot(WORKSPACE_ID)
    assert snapshot.available[0].body == "Check correctness."
    service.paths.skills_dir.joinpath("review", "SKILL.md").write_text(CONTENT + "\nChanged.")
    assert service.snapshot(WORKSPACE_ID).available[0].body.endswith("Changed.")
    assert snapshot.available[0].body == "Check correctness."


def test_workspace_precedence_and_master_switch(tmp_path):
    service = setup(tmp_path)
    item = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)["skill"]
    service.configure(expected=1, identifier=item["id"], enabled=True)
    local = service.save(scope="workspace", workspace_id=WORKSPACE_ID, content=CONTENT, expected=2)["skill"]
    service.configure(expected=3, identifier=local["id"], enabled=False)
    assert not service.snapshot(WORKSPACE_ID).available
    service.configure(expected=4, identifier=local["id"], enabled=True)
    assert service.snapshot(WORKSPACE_ID).available
    service.configure(expected=5, enabled=False)
    assert not service.snapshot(WORKSPACE_ID).available


def test_workspace_files_are_local_and_archive_preserves_content(tmp_path):
    service = setup(tmp_path)
    item = service.save(scope="workspace", workspace_id=WORKSPACE_ID, content=CONTENT, expected=0)["skill"]
    path = service.paths.managed_workspaces_dir / "project" / "skills" / "review" / "SKILL.md"
    assert path.read_text() == CONTENT
    service.delete(item["id"], 1)
    assert not path.exists()
    assert next(service.paths.skills_archive_dir.glob("*/SKILL.md")).read_text() == CONTENT


@pytest.mark.parametrize("content", [CONTENT.replace("name: review", "name: review\nname: other"), CONTENT.replace("description:", "unknown:"), "---\nname: x\ndescription: y\n---\n", CONTENT + "x" * 65536], ids=["duplicate", "unknown", "empty", "oversized"])
def test_bad_documents_are_rejected(content):
    with pytest.raises(SkillError):
        parse(content)


def test_corrupt_catalog_does_not_break_plain_snapshot(tmp_path):
    service = setup(tmp_path)
    service.paths.skills_settings_file.parent.mkdir(parents=True, exist_ok=True)
    service.paths.skills_settings_file.write_text("{}")
    assert not service.snapshot(WORKSPACE_ID).available
    with pytest.raises(SkillError):
        service.snapshot(WORKSPACE_ID, ("unknown",))


def test_catalog_accepts_legacy_unicode_directory_names(tmp_path):
    service = setup(tmp_path)
    legacy_directory = "😀" * 64
    service.paths.skills_settings_file.parent.mkdir(parents=True, exist_ok=True)
    service.paths.skills_settings_file.write_text(json.dumps({
        "version": 1,
        "revision": 7,
        "enabled": True,
        "skills": [{
            "id": "11111111-1111-4111-8111-111111111111",
            "scope": "global",
            "workspaceId": None,
            "directoryName": legacy_directory,
            "name": legacy_directory,
            "description": "Legacy Windows Skill",
            "revision": 1,
            "enabled": False,
            "confirmedHash": None,
            "disabledWorkspaces": [],
        }],
    }), encoding="utf-8")

    assert service.settings() == {"enabled": True, "revision": 8}
    assert service.list("global")["skills"][0]["directoryName"] == legacy_directory


def test_transaction_recovers_file_write_before_catalog(tmp_path, monkeypatch):
    service = setup(tmp_path)
    import opensprite_backend.skills.service as module
    original = module.atomic_write
    def fail_catalog(path, data):
        if path == service.paths.skills_settings_file:
            raise OSError
        original(path, data)
    monkeypatch.setattr(module, "atomic_write", fail_catalog)
    with pytest.raises(SkillError):
        service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)
    monkeypatch.setattr(module, "atomic_write", original)
    assert service.list("global")["skills"][0]["name"] == "review"
    assert not service.paths.skills_transaction_file.exists()


def test_missing_skill_can_be_removed_without_blocking_catalog(tmp_path):
    service = setup(tmp_path)
    item = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)["skill"]
    path = service.paths.skills_dir / "review" / "SKILL.md"
    path.unlink()
    path.parent.rmdir()
    service.delete(item["id"], 1)
    assert service.list("global")["skills"] == []
    assert not service.paths.skills_transaction_file.exists()


def test_scope_same_names_and_workspace_removal_disable_registry(tmp_path):
    service = setup(tmp_path)
    global_item = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)["skill"]
    local = service.save(scope="workspace", workspace_id=WORKSPACE_ID, content=CONTENT, expected=1)["skill"]
    service.configure(expected=2, identifier=local["id"], enabled=True)
    service.forget_workspace(WORKSPACE_ID)
    assert service.list("workspace", WORKSPACE_ID)["skills"] == []
    assert service.snapshot(WORKSPACE_ID).available[0].id == global_item["id"]
    assert (service.paths.managed_workspaces_dir / "project" / "skills" / "review" / "SKILL.md").exists()


@pytest.mark.parametrize("scope", ["global", "workspace"])
def test_scan_enables_valid_new_skills_and_preserves_existing_toggle(tmp_path, scope):
    service = setup(tmp_path)
    workspace_id = WORKSPACE_ID if scope == "workspace" else None
    base = service.paths.skills_dir if scope == "global" else service.paths.managed_workspaces_dir / "project/skills"
    directory = base / "review"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(CONTENT, encoding="utf-8")
    item = service.scan(scope, workspace_id, 0)["skills"][0]
    assert item["enabled"] and item["effective"]
    assert service.snapshot(WORKSPACE_ID).available[0].id == item["id"]
    service.configure(expected=1, identifier=item["id"], enabled=False)
    again = service.scan(scope, workspace_id, 2)["skills"][0]
    assert again["id"] == item["id"] and not again["enabled"]


def test_scan_does_not_override_master_switch(tmp_path):
    service = setup(tmp_path)
    service.configure(expected=0, enabled=False)
    directory = service.paths.skills_dir / "review"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(CONTENT, encoding="utf-8")
    item = service.scan("global", None, 1)["skills"][0]
    assert item["enabled"] and not item["effective"]
    assert not service.snapshot(WORKSPACE_ID).available


def test_scan_registers_invalid_documents_without_enabling(tmp_path):
    service = setup(tmp_path)
    directory = service.paths.skills_dir / "broken"
    directory.mkdir(parents=True)
    directory.joinpath("SKILL.md").write_text("invalid", encoding="utf-8")
    result = service.scan("global", None, 0)
    assert result["skills"][0]["state"] == "invalid_format"
    assert not result["skills"][0]["enabled"]
    assert not service.snapshot(WORKSPACE_ID).available
