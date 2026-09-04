"""Workspace catalog persistence, policy, service, and HTTP tests."""

from __future__ import annotations

from asyncio import run
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from opensprite_backend.app import create_app
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.runtime import create_system_app
import opensprite_backend.workspaces.policy as workspace_policy
from opensprite_backend.workspaces import (
    UNASSIGNED_WORKSPACE_ID,
    JsonWorkspaceStore,
    WorkspaceCatalogService,
    WorkspaceCatalogState,
    WorkspaceError,
    WorkspaceFailure,
    WorkspaceRootPolicy,
    WorkspaceRecord,
    WorkspaceStoreError,
    WorkspaceUsage,
)


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
SECOND_ID = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 9, 4, 3, 0, tzinfo=timezone.utc)


class UsageReader:
    def __init__(self) -> None:
        self.values: dict[str, WorkspaceUsage] = {}

    def workspace_usage(self, workspace_id: str) -> WorkspaceUsage:
        return self.values.get(workspace_id, WorkspaceUsage())


def make_service(
    tmp_path: Path,
    *,
    usage: UsageReader | None = None,
    identifiers: list[str] | None = None,
) -> tuple[WorkspaceCatalogService, Path, Path]:
    data_root = tmp_path / ".opensprite"
    install_root = tmp_path / "installed-app"
    user_home = tmp_path / "home"
    project_root = tmp_path / "projects" / "alpha"
    install_root.mkdir()
    user_home.mkdir()
    project_root.mkdir(parents=True)
    values = iter(identifiers or [WORKSPACE_ID, SECOND_ID])
    return (
        WorkspaceCatalogService(
            JsonWorkspaceStore(data_root / "config" / "workspaces.json"),
            WorkspaceRootPolicy(
                data_root=data_root,
                install_root=install_root,
                user_home=user_home,
            ),
            usage_reader=usage,
            clock=lambda: NOW,
            identifier_factory=lambda: next(values),
        ),
        data_root,
        project_root,
    )


def test_missing_store_is_lazy_and_exposes_only_unassigned(tmp_path: Path) -> None:
    service, data_root, _ = make_service(tmp_path)

    catalog = run(service.list())

    assert catalog.revision == 0
    assert catalog.active_workspace_id == UNASSIGNED_WORKSPACE_ID
    assert [item.kind.value for item in catalog.workspaces] == ["unassigned"]
    assert not data_root.exists()


def test_create_normalizes_name_persists_atomically_and_sets_active(tmp_path: Path) -> None:
    service, data_root, project_root = make_service(tmp_path)

    created = run(
        service.create(
            name="  Cafe\u0301  ",
            root_path=str(project_root),
            expected_revision=0,
        )
    )

    assert created.revision == 1
    assert created.active_workspace_id == WORKSPACE_ID
    item = created.workspaces[1]
    assert item.name == "Caf\u00e9"
    assert item.root_path == str(project_root.resolve())
    assert item.availability.value == "available"
    payload = json.loads(
        (data_root / "config" / "workspaces.json").read_text(encoding="utf-8")
    )
    assert payload["activeWorkspaceId"] == WORKSPACE_ID
    assert payload["workspaces"][0]["rootPath"] == str(project_root.resolve())


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":1,"version":1,"revision":0,"activeWorkspaceId":"00000000-0000-4000-8000-000000000000","workspaces":[]}',
        '{"version":2,"revision":0,"activeWorkspaceId":"00000000-0000-4000-8000-000000000000","workspaces":[]}',
        '{"version":1,"revision":0,"activeWorkspaceId":"11111111-1111-4111-8111-111111111111","workspaces":[]}',
    ],
)
def test_store_rejects_malformed_input(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "workspaces.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(WorkspaceStoreError) as raised:
        JsonWorkspaceStore(path).get()

    assert str(raised.value) == "Workspace settings are unavailable."
    assert raised.value.__cause__ is None


def test_atomic_failure_preserves_previous_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, data_root, project_root = make_service(tmp_path)
    run(service.create(name="Alpha", root_path=str(project_root), expected_revision=0))
    path = data_root / "config" / "workspaces.json"
    before = path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("private failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(WorkspaceError) as raised:
        run(
            service.set_active(
                UNASSIGNED_WORKSPACE_ID,
                expected_revision=1,
            )
        )

    assert raised.value.failure is WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE
    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_root_policy_rejects_high_risk_and_duplicate_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, data_root, project_root = make_service(tmp_path)
    run(service.create(name="Alpha", root_path=str(project_root), expected_revision=0))

    for unsafe in (tmp_path / "home", data_root, tmp_path / "installed-app"):
        unsafe.mkdir(parents=True, exist_ok=True)
        with pytest.raises(WorkspaceError) as raised:
            run(service.create(name="Unsafe", root_path=str(unsafe), expected_revision=1))
        assert raised.value.failure is WorkspaceFailure.UNSAFE_ROOT

    with pytest.raises(WorkspaceError) as duplicate:
        run(service.create(name="Other", root_path=str(project_root), expected_revision=1))
    assert duplicate.value.failure is WorkspaceFailure.DUPLICATE_ROOT

    second_root = tmp_path / "projects" / "beta"
    second_root.mkdir()
    with pytest.raises(WorkspaceError) as duplicate_name:
        run(service.create(name="alpha", root_path=str(second_root), expected_revision=1))
    assert duplicate_name.value.failure is WorkspaceFailure.DUPLICATE_NAME

    junction_root = tmp_path / "projects" / "junction"
    junction_root.mkdir()
    monkeypatch.setattr(
        service._root_policy,
        "_is_junction",
        lambda path: path == junction_root,
    )
    with pytest.raises(WorkspaceError) as junction:
        run(service.create(name="Junction", root_path=str(junction_root), expected_revision=1))
    assert junction.value.failure is WorkspaceFailure.UNSAFE_ROOT


def test_windows_reparse_attribute_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, project_root = make_service(tmp_path)
    fake_path = SimpleNamespace(
        lstat=lambda: SimpleNamespace(st_file_attributes=0x400)
    )
    original_os_name = workspace_policy.os.name
    monkeypatch.setattr(workspace_policy.os, "name", "nt")
    assert WorkspaceRootPolicy._is_reparse_point(fake_path) is True
    monkeypatch.setattr(workspace_policy.os, "name", original_os_name)
    monkeypatch.setattr(service._root_policy, "_is_reparse_point", lambda _path: True)

    with pytest.raises(WorkspaceError) as reparse:
        run(service.create(name="Reparse", root_path=str(project_root), expected_revision=0))

    assert reparse.value.failure is WorkspaceFailure.UNSAFE_ROOT


def test_symlink_root_is_rejected(tmp_path: Path) -> None:
    service, _, project_root = make_service(tmp_path)
    link = tmp_path / "projects" / "linked-root"
    try:
        link.symlink_to(project_root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink is unavailable: {type(error).__name__}")

    with pytest.raises(WorkspaceError) as symlink:
        run(service.create(name="Symlink", root_path=str(link), expected_revision=0))

    assert symlink.value.failure is WorkspaceFailure.UNSAFE_ROOT


def test_workspace_limit_rejects_the_101st_user_workspace(tmp_path: Path) -> None:
    store = JsonWorkspaceStore(tmp_path / ".opensprite" / "config" / "workspaces.json")
    records = tuple(
        WorkspaceRecord(
            id=f"{index:08x}-0000-4000-8000-{index:012x}",
            name=f"Workspace {index}",
            root_path=str(tmp_path / "projects" / str(index)),
            revision=1,
            created_at=NOW,
            updated_at=NOW,
        )
        for index in range(1, 101)
    )
    store.set(WorkspaceCatalogState(100, UNASSIGNED_WORKSPACE_ID, records))
    project_root = tmp_path / "project"
    project_root.mkdir()
    service = WorkspaceCatalogService(
        store,
        WorkspaceRootPolicy(
            data_root=tmp_path / ".opensprite",
            user_home=tmp_path / "home",
            install_root=tmp_path / "installed-app",
        ),
    )

    with pytest.raises(WorkspaceError) as maximum:
        run(
            service.create(
                name="One too many",
                root_path=str(project_root),
                expected_revision=100,
            )
        )

    assert maximum.value.failure is WorkspaceFailure.INVALID_REQUEST


def test_update_delete_and_usage_guards(tmp_path: Path) -> None:
    usage = UsageReader()
    service, _, project_root = make_service(tmp_path, usage=usage)
    run(service.create(name="Alpha", root_path=str(project_root), expected_revision=0))
    replacement = tmp_path / "projects" / "beta"
    replacement.mkdir()

    usage.values[WORKSPACE_ID] = WorkspaceUsage(active_run_count=1)
    with pytest.raises(WorkspaceError) as busy:
        run(
            service.update(
                WORKSPACE_ID,
                name="Beta",
                root_path=str(replacement),
                expected_revision=1,
            )
        )
    assert busy.value.failure is WorkspaceFailure.WORKSPACE_BUSY

    usage.values[WORKSPACE_ID] = WorkspaceUsage(conversation_count=1)
    with pytest.raises(WorkspaceError) as not_empty:
        run(service.delete(WORKSPACE_ID, expected_revision=1))
    assert not_empty.value.failure is WorkspaceFailure.WORKSPACE_NOT_EMPTY

    usage.values[WORKSPACE_ID] = WorkspaceUsage()
    run(service.delete(WORKSPACE_ID, expected_revision=1))
    catalog = run(service.list())
    assert catalog.active_workspace_id == UNASSIGNED_WORKSPACE_ID
    assert len(catalog.workspaces) == 1


def test_api_crud_strict_json_and_sanitized_errors(tmp_path: Path) -> None:
    service, _, project_root = make_service(tmp_path)
    with TestClient(create_app(workspaces=service)) as client:
        initial = client.get("/api/workspaces")
        duplicate_json = client.post(
            "/api/workspaces",
            content=(
                '{"name":"Alpha","name":"Beta","rootPath":'
                + json.dumps(str(project_root))
                + ',"expectedRevision":0}'
            ),
            headers={"Content-Type": "application/json"},
        )
        created = client.post(
            "/api/workspaces",
            json={
                "name": "Alpha",
                "rootPath": str(project_root),
                "expectedRevision": 0,
            },
        )
        conflict = client.put(
            "/api/workspaces/active",
            json={
                "workspaceId": UNASSIGNED_WORKSPACE_ID,
                "expectedRevision": 0,
            },
        )
        fetched = client.get(f"/api/workspaces/{WORKSPACE_ID}")
        invalid_deletes = [
            client.delete(f"/api/workspaces/{WORKSPACE_ID}"),
            client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=1&unexpected=1"),
            client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=1&expectedRevision=2"),
            client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=0"),
            client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=-1"),
            client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=invalid"),
        ]
        removed = client.delete(
            f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=1"
        )

    assert initial.status_code == 200
    assert initial.json()["workspaces"][0]["kind"] == "unassigned"
    assert duplicate_json.status_code == 400
    assert duplicate_json.json()["error"]["code"] == "invalid_request"
    assert created.status_code == 201
    assert created.json()["activeWorkspaceId"] == WORKSPACE_ID
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "revision_conflict"
    assert fetched.status_code == 200
    assert fetched.json()["rootPath"] == str(project_root.resolve())
    assert all(item.status_code == 400 for item in invalid_deletes)
    assert all(item.json()["error"]["code"] == "invalid_request" for item in invalid_deletes)
    assert removed.status_code == 204


def test_workspace_api_obeys_same_origin_protection(tmp_path: Path) -> None:
    service, _, project_root = make_service(tmp_path)
    app = create_app(workspaces=service, enforce_local_security=True)
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.post(
            "/api/workspaces",
            headers={"Origin": "http://evil.example"},
            json={
                "name": "Alpha",
                "rootPath": str(project_root),
                "expectedRevision": 0,
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_app_paths_owns_workspace_config_location(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    assert paths.workspace_settings_file == paths.home / "config" / "workspaces.json"


def test_system_runtime_exposes_lazy_unassigned_workspace(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    app = create_system_app(app_paths=paths, enforce_authentication=False)

    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/workspaces")

    assert response.status_code == 200
    assert response.json()["activeWorkspaceId"] == UNASSIGNED_WORKSPACE_ID
    assert response.json()["workspaces"][0]["usage"] == {
        "conversationCount": 0,
        "scheduleCount": 0,
        "activeRunCount": 0,
    }
    assert not paths.workspace_settings_file.exists()
