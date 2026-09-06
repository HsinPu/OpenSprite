"""Skills approval, scoping and immutable content tests."""
from asyncio import run
import pytest
from opensprite_backend.app_paths import AppPaths
from opensprite_backend.skills.format import parse
from opensprite_backend.skills.models import SkillError
from opensprite_backend.skills.service import SkillsService
from test_workspaces import make_service, WORKSPACE_ID

CONTENT = "---\nname: review\ndescription: Review code\n---\nCheck correctness."


def setup(tmp_path):
    workspaces, data, _, _ = make_service(tmp_path)
    run(workspaces.startup())
    run(workspaces.create(name="project", expected_revision=0))
    return SkillsService(AppPaths(data), workspaces)


def test_approval_scope_and_frozen_snapshot(tmp_path):
    service = setup(tmp_path)
    created = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)
    item = created["skill"]
    assert not service.snapshot(WORKSPACE_ID).available
    service.configure(expected=1, identifier=item["id"], enabled=True, confirmed_hash=item["contentHash"])
    snapshot = service.snapshot(WORKSPACE_ID)
    assert snapshot.available[0].body == "Check correctness."
    service.paths.skills_dir.joinpath("review", "SKILL.md").write_text(CONTENT + "\nChanged.")
    assert not service.snapshot(WORKSPACE_ID).available
    assert snapshot.available[0].body == "Check correctness."


def test_workspace_override_and_master_switch(tmp_path):
    service = setup(tmp_path)
    item = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)["skill"]
    service.configure(expected=1, identifier=item["id"], enabled=True, confirmed_hash=item["contentHash"])
    service.configure(expected=2, identifier=item["id"], workspace_id=WORKSPACE_ID, disabled=True)
    assert not service.snapshot(WORKSPACE_ID).available
    service.configure(expected=3, identifier=item["id"], workspace_id=WORKSPACE_ID, disabled=False)
    assert service.snapshot(WORKSPACE_ID).available
    service.configure(expected=4, enabled=False)
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
