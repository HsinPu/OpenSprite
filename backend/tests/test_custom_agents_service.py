"""Filesystem, policy, and transaction tests for custom Agent management."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from opensprite_backend.app_paths import AppPaths
from opensprite_backend.custom_agents.models import AgentError
from opensprite_backend.custom_agents.service import CustomAgentsService
from test_workspaces import WORKSPACE_ID, make_service


CONTENT = (
    'name = "review"\n'
    'description = "Review code"\n'
    'developer_instructions = "Return evidence"\n'
)


def build(tmp_path: Path) -> tuple[CustomAgentsService, object, Path]:
    workspaces, data_root, managed_root, _ = make_service(tmp_path)
    asyncio.run(workspaces.startup())
    asyncio.run(workspaces.create(name="project", expected_revision=0))
    return CustomAgentsService(AppPaths(data_root), workspaces), workspaces, managed_root


def test_create_get_list_and_remove_archive(tmp_path: Path) -> None:
    service, _, _ = build(tmp_path)

    created = service.create("global", None, CONTENT, 0)
    assert "content" not in created
    assert created["reason"] == "effective"
    assert created["contentHash"]

    listed = service.list_agents("global", None)
    assert listed["revision"] == 1
    assert set(listed["items"][0]) == {
        "id",
        "scope",
        "workspaceId",
        "fileName",
        "name",
        "description",
        "revision",
        "enabled",
        "reason",
        "shadowedByAgentId",
        "providerId",
        "model",
        "contentHash",
    }
    detail = service.get(str(created["id"]))
    assert detail["content"] == CONTENT

    service.remove(str(created["id"]), 1)
    assert service.list_agents("global", None)["items"] == []
    assert list(service.paths.agents_archive_dir.rglob("*.toml"))


@pytest.mark.parametrize("literal,expected", [
    ("'Return evidence' # comment", "Return evidence"),
    ('"""Return\\nquoted \\"evidence\\""""', 'Return\nquoted "evidence"'),
    ("'''Return evidence'''", "Return evidence"),
])
def test_detail_exposes_parsed_instructions(tmp_path: Path, literal: str, expected: str) -> None:
    service, _, _ = build(tmp_path)
    content = 'name = "review"\ndescription = "Review"\ndeveloper_instructions = ' + literal + '\n'
    created = service.create("global", None, content, 0)
    assert service.get(str(created["id"]))["developerInstructions"] == expected


def test_workspace_same_name_shadows_global_and_remove_restores(tmp_path: Path) -> None:
    service, _, _ = build(tmp_path)
    global_item = service.create("global", None, CONTENT, 0)
    local_item = service.create("workspace", WORKSPACE_ID, CONTENT, 1)

    view = service.list_agents("workspace", WORKSPACE_ID)
    global_view = next(item for item in view["items"] if item["id"] == global_item["id"])
    local_view = next(item for item in view["items"] if item["id"] == local_item["id"])
    assert global_view["reason"] == "shadowed_by_workspace"
    assert global_view["shadowedByAgentId"] == local_item["id"]
    assert local_view["reason"] == "effective"
    assert [item.record.id for item in service.snapshot(WORKSPACE_ID).available] == [
        local_item["id"]
    ]

    service.remove(str(local_item["id"]), 2)
    restored = service.list_agents("workspace", WORKSPACE_ID)
    assert next(item for item in restored["items"] if item["id"] == global_item["id"])["reason"] == "effective"


def test_workspace_unavailable_keeps_local_shadow_and_fails_closed(tmp_path: Path) -> None:
    service, _, managed_root = build(tmp_path)
    global_item = service.create("global", None, CONTENT, 0)
    local_item = service.create("workspace", WORKSPACE_ID, CONTENT, 1)
    context = service.workspaces.execution_context(WORKSPACE_ID)
    Path(context.root_path).rename(managed_root / "gone")

    view = service.list_agents("workspace", WORKSPACE_ID)
    global_view = next(item for item in view["items"] if item["id"] == global_item["id"])
    local_view = next(item for item in view["items"] if item["id"] == local_item["id"])
    assert global_view["reason"] == "shadowed_by_workspace"
    assert local_view["reason"] == "workspace_unavailable"
    assert not service.snapshot(WORKSPACE_ID).available
    assert service.snapshot(WORKSPACE_ID) is not None


def test_scan_registers_only_valid_files_and_enables_by_default(tmp_path: Path) -> None:
    service, _, _ = build(tmp_path)
    service.paths.agents_dir.mkdir(parents=True)
    (service.paths.agents_dir / "review.toml").write_text(CONTENT, encoding="utf-8")
    (service.paths.agents_dir / "invalid.toml").write_text("name = 1\n", encoding="utf-8")

    result = service.scan("global", None, 0)
    assert result == {"added": 1, "revision": 1}
    item = service.list_agents("global", None)["items"][0]
    assert item["enabled"] is True
    assert service.scan("global", None, 1) == {"added": 0, "revision": 1}


def test_update_and_batch_are_catalog_revision_checked_and_atomic(tmp_path: Path) -> None:
    service, _, _ = build(tmp_path)
    first = service.create("global", None, CONTENT, 0)
    second_content = CONTENT.replace("review", "writing")
    second = service.create("global", None, second_content, 1)

    with pytest.raises(AgentError, match="revision_conflict"):
        service.update(str(first["id"]), CONTENT, 1)
    with pytest.raises(AgentError, match="invalid_request"):
        service.batch("global", None, [str(first["id"]), WORKSPACE_ID], "disable", 2)
    assert service.settings()["revision"] == 2


def test_failed_catalog_write_recovers_from_transaction_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _ = build(tmp_path)
    original = service.store.write
    calls = 0

    def fail_once(catalog):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AgentError("store_unavailable")
        return original(catalog)

    monkeypatch.setattr(service.store, "write", fail_once)
    with pytest.raises(AgentError, match="store_unavailable"):
        service.create("global", None, CONTENT, 0)
    assert service.paths.agents_transaction_file.exists()

    monkeypatch.setattr(service.store, "write", original)
    assert service.settings()["revision"] == 1
    assert not service.paths.agents_transaction_file.exists()
    assert service.list_agents("global", None)["items"]


def test_remove_workspace_only_removes_registration(tmp_path: Path) -> None:
    service, _, managed_root = build(tmp_path)
    item = service.create("workspace", WORKSPACE_ID, CONTENT, 0)
    path = managed_root / "project" / "agents" / str(item["fileName"])
    assert path.exists()

    service.remove_workspace(WORKSPACE_ID)
    assert not service.list_agents("workspace", WORKSPACE_ID)["items"]
    assert path.exists()
