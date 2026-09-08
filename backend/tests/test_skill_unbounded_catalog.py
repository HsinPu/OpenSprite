"""Skill count is not capped; content and execution protections remain separate."""
import pytest

from opensprite_backend.api.skill_routes import BatchResponse
from opensprite_backend.skills.service import SkillsService
from test_skills import CONTENT, WORKSPACE_ID, setup


@pytest.mark.parametrize("scope", ["global", "workspace"])
def test_scan_create_and_archive_more_than_100(tmp_path, scope):
    service = setup(tmp_path)
    workspace_id = WORKSPACE_ID if scope == "workspace" else None
    base = service._base(scope, workspace_id)
    for index in range(297):
        folder = base / f"skill-{index}"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(CONTENT.replace("name: review", f"name: skill-{index}"), encoding="utf-8")
    result = service.scan(scope, workspace_id, 0)
    assert len(result["skills"]) == 297
    assert all(item["enabled"] for item in result["skills"])
    service = SkillsService(service.paths, service.workspaces)
    assert len(service.list(scope, workspace_id)["skills"]) == 297
    service.save(scope=scope, workspace_id=workspace_id, content=CONTENT, expected=result["revision"])
    for action in ("disable", "enable", "archive"):
        result = service.batch(scope=scope, workspace_id=workspace_id, action=action, expected=service.settings()["revision"])
        assert BatchResponse.model_validate(result).completed == 298
    assert not service.list(scope, workspace_id)["skills"]
    assert len(list(service.paths.skills_archive_dir.glob("*/SKILL.md"))) == 298
