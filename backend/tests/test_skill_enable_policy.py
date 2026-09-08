import json
import pytest
from test_skills import CONTENT, setup, WORKSPACE_ID


def test_import_and_edits_preserve_explicit_toggle(tmp_path):
    service = setup(tmp_path)
    item = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)["skill"]
    assert item["enabled"] and item["effective"]
    service.configure(expected=1, identifier=item["id"], enabled=False)
    service.save(scope="global", workspace_id=None, content=CONTENT + "\nUpdate", expected=2, identifier=item["id"])
    assert not service.get(item["id"])["skill"]["enabled"]
    service.configure(expected=3, identifier=item["id"], enabled=True)
    frozen = service.snapshot(WORKSPACE_ID)
    path = service.paths.skills_dir / "review/SKILL.md"
    path.write_text(CONTENT + "\nExternal", encoding="utf-8")
    assert service.snapshot(WORKSPACE_ID).available[0].body.endswith("External")
    assert frozen.available[0].body.endswith("Update")
    path.write_text("invalid", encoding="utf-8")
    assert not service.snapshot(WORKSPACE_ID).available
    assert service.get(item["id"])["skill"]["state"] == "invalid_format"


@pytest.mark.parametrize("enabled,confirmed,expected", [(True, True, True), (True, False, True), (False, False, False)])
def test_v1_upgrade_preserves_explicit_enabled_state(tmp_path, enabled, confirmed, expected):
    service = setup(tmp_path)
    item = service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)["skill"]
    path = service.paths.skills_settings_file
    catalog = json.loads(path.read_text())
    catalog["version"] = 1
    catalog["skills"][0]["enabled"] = enabled
    catalog["skills"][0]["confirmedHash"] = item["contentHash"] if confirmed else None
    path.write_text(json.dumps(catalog), encoding="utf-8")
    assert service.get(item["id"])["skill"]["enabled"] is expected
    saved = json.loads(path.read_text())
    assert saved["version"] == 3 and saved["revision"] == 2
    assert service.settings()["revision"] == 2


def test_migration_write_failure_preserves_v1(tmp_path, monkeypatch):
    service = setup(tmp_path)
    service.save(scope="global", workspace_id=None, content=CONTENT, expected=0)
    path = service.paths.skills_settings_file
    catalog = json.loads(path.read_text()); catalog["version"] = 1
    path.write_text(json.dumps(catalog), encoding="utf-8")
    import opensprite_backend.skills.service as module
    original = module.atomic_write
    def fail(*args):
        raise OSError("injected")
    monkeypatch.setattr(module, "atomic_write", fail)
    assert not service.snapshot(WORKSPACE_ID).available
    assert json.loads(path.read_text())["version"] == 1
    monkeypatch.setattr(module, "atomic_write", original)
    assert service.settings()["revision"] == 2
