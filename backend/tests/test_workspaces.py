"""Managed Workspace catalog, mount, migration, policy, and HTTP tests."""

from __future__ import annotations

from asyncio import run
from dataclasses import replace
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
    DEFAULT_WORKSPACE_ID,
    JsonWorkspaceStore,
    WorkspaceAvailability,
    WorkspaceCatalogService,
    WorkspaceError,
    WorkspaceFailure,
    WorkspaceMountAccess,
    WorkspaceRootPolicy,
    WorkspaceStoreError,
    WorkspaceUsage,
)


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
SECOND_ID = "22222222-2222-4222-8222-222222222222"
MOUNT_ID = "33333333-3333-4333-8333-333333333333"
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
) -> tuple[WorkspaceCatalogService, Path, Path, Path]:
    data_root = tmp_path / ".opensprite"
    install_root = tmp_path / "installed-app"
    user_home = tmp_path / "home"
    managed_root = tmp_path / "OpenSprite" / "workspace"
    external_root = tmp_path / "projects" / "alpha"
    install_root.mkdir()
    user_home.mkdir()
    external_root.mkdir(parents=True)
    values = iter(identifiers or [WORKSPACE_ID, SECOND_ID, MOUNT_ID])
    return (
        WorkspaceCatalogService(
            JsonWorkspaceStore(data_root / "config" / "workspaces.json"),
            WorkspaceRootPolicy(
                data_root=data_root,
                install_root=install_root,
                user_home=user_home,
            ),
            managed_root,
            usage_reader=usage,
            clock=lambda: NOW,
            identifier_factory=lambda: next(values),
        ),
        data_root,
        managed_root,
        external_root,
    )


def test_startup_creates_fixed_default_workspace_without_catalog_file(tmp_path: Path) -> None:
    service, data_root, managed_root, _ = make_service(tmp_path)

    run(service.startup())
    catalog = run(service.list())

    assert catalog.revision == 0
    assert catalog.active_workspace_id == DEFAULT_WORKSPACE_ID
    assert [item.kind.value for item in catalog.workspaces] == ["default"]
    assert catalog.workspaces[0].name == "Default workspace"
    assert catalog.workspaces[0].root_path == str((managed_root / "default").resolve())
    assert catalog.workspaces[0].availability is WorkspaceAvailability.AVAILABLE
    assert (managed_root / "default").is_dir()
    assert not data_root.exists()


def test_default_root_creation_failure_keeps_text_workspace_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, managed_root, _ = make_service(tmp_path)
    monkeypatch.setattr(service, "_ensure_directory", lambda _path: (_ for _ in ()).throw(WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)))

    run(service.startup())
    catalog = run(service.list())

    assert catalog.workspaces[0].availability is WorkspaceAvailability.UNAVAILABLE
    assert catalog.workspaces[0].unavailable_reason.value == "missing"
    assert not managed_root.exists()


def test_create_uses_name_as_managed_directory_and_sets_active(tmp_path: Path) -> None:
    service, data_root, managed_root, _ = make_service(tmp_path)
    run(service.startup())

    created = run(service.create(name="Test", expected_revision=0))

    assert created.revision == 1
    assert created.active_workspace_id == WORKSPACE_ID
    item = created.workspaces[1]
    assert item.name == "Test"
    assert item.directory_name == "Test"
    assert item.root_path == str((managed_root / "Test").resolve())
    assert (managed_root / "Test").is_dir()
    payload = json.loads(
        (data_root / "config" / "workspaces.json").read_text(encoding="utf-8")
    )
    assert payload["version"] == 2
    assert payload["workspaces"][0]["directoryName"] == "Test"
    assert "rootPath" not in payload["workspaces"][0]


@pytest.mark.parametrize(
    "name",
    [
        ".",
        "..",
        "CON",
        "aux.txt",
        "bad/name",
        "bad\\name",
        "bad:name",
        "trailing.",
        "trailing ",
        "control\x7f",
        "format\u202e",
    ],
)
def test_create_rejects_unsafe_cross_platform_directory_names(
    tmp_path: Path, name: str
) -> None:
    service, _, _, _ = make_service(tmp_path)

    with pytest.raises(WorkspaceError) as raised:
        run(service.create(name=name, expected_revision=0))

    assert raised.value.failure is WorkspaceFailure.INVALID_DIRECTORY_NAME


@pytest.mark.parametrize(
    "name",
    [
        "developer-\U0001f468\u200d\U0001f4bb",
        "joiner-\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",
    ],
)
def test_create_accepts_safe_unicode_joiners(tmp_path: Path, name: str) -> None:
    service, _, managed_root, _ = make_service(tmp_path)
    run(service.startup())

    created = run(service.create(name=name, expected_revision=0))

    assert created.workspaces[1].name == name
    assert created.workspaces[1].directory_name == name
    assert (managed_root / name).is_dir()


def test_root_policy_rejects_parents_that_contain_protected_roots(
    tmp_path: Path,
) -> None:
    user_home = tmp_path / "home"
    data_root = user_home / ".opensprite"
    install_root = user_home / "apps" / "OpenSprite"
    safe_root = user_home / "projects" / "safe"
    for path in (data_root, install_root, safe_root):
        path.mkdir(parents=True)
    policy = WorkspaceRootPolicy(
        data_root=data_root,
        install_root=install_root,
        user_home=user_home,
    )

    for unsafe in (tmp_path, user_home / "apps"):
        with pytest.raises(workspace_policy.UnsafeWorkspaceRoot):
            policy.validate_new_root(str(unsafe))

    assert policy.validate_new_root(str(safe_root)) == str(safe_root.resolve())


def test_create_does_not_adopt_existing_directory_and_import_is_explicit(
    tmp_path: Path,
) -> None:
    service, _, managed_root, _ = make_service(tmp_path)
    run(service.startup())
    existing = managed_root / "Existing"
    existing.mkdir()

    with pytest.raises(WorkspaceError) as raised:
        run(service.create(name="Existing", expected_revision=0))
    assert raised.value.failure is WorkspaceFailure.MANAGED_ROOT_EXISTS

    page = run(service.import_candidates(limit=50, before=None))
    assert [(item.directory_name, item.root_path) for item in page.candidates] == [
        ("Existing", str(existing.resolve()))
    ]
    imported = run(
        service.import_existing(directory_name="Existing", expected_revision=0)
    )
    assert imported.active_workspace_id == WORKSPACE_ID
    assert imported.workspaces[1].directory_name == "Existing"


def test_import_candidates_are_cursor_paginated(tmp_path: Path) -> None:
    service, _, managed_root, _ = make_service(tmp_path)
    run(service.startup())
    for name in ("Alpha", "Beta", "Gamma"):
        (managed_root / name).mkdir()

    first = run(service.import_candidates(limit=2, before=None))
    second = run(service.import_candidates(limit=2, before=first.next_cursor))

    assert [item.directory_name for item in first.candidates] == ["Alpha", "Beta"]
    assert first.next_cursor is not None
    assert [item.directory_name for item in second.candidates] == ["Gamma"]
    assert second.next_cursor is None


def test_v1_migration_creates_managed_root_and_preserves_external_root_as_mount(
    tmp_path: Path,
) -> None:
    service, data_root, managed_root, external_root = make_service(tmp_path)
    path = data_root / "config" / "workspaces.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "revision": 1,
                "activeWorkspaceId": WORKSPACE_ID,
                "workspaces": [
                    {
                        "id": WORKSPACE_ID,
                        "name": "Legacy",
                        "rootPath": str(external_root.resolve()),
                        "revision": 1,
                        "createdAt": NOW.isoformat(),
                        "updatedAt": NOW.isoformat(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    run(service.startup())
    catalog = run(service.list())

    assert (managed_root / "Legacy").is_dir()
    legacy = catalog.workspaces[1]
    assert legacy.root_path == str((managed_root / "Legacy").resolve())
    assert len(legacy.mounts) == 1
    assert legacy.mounts[0].alias == "legacy-root"
    assert legacy.mounts[0].root_path == str(external_root.resolve())
    assert legacy.mounts[0].access_mode is WorkspaceMountAccess.READ_WRITE
    assert legacy.mounts[0].enabled is True
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2
    assert external_root.is_dir()


@pytest.mark.parametrize("legacy_name", ["default", "Default workspace"])
def test_v1_migration_renames_values_reserved_by_the_default_workspace(
    tmp_path: Path,
    legacy_name: str,
) -> None:
    service, data_root, managed_root, external_root = make_service(tmp_path)
    path = data_root / "config" / "workspaces.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "revision": 1,
                "activeWorkspaceId": WORKSPACE_ID,
                "workspaces": [
                    {
                        "id": WORKSPACE_ID,
                        "name": legacy_name,
                        "rootPath": str(external_root.resolve()),
                        "revision": 1,
                        "createdAt": NOW.isoformat(),
                        "updatedAt": NOW.isoformat(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    run(service.startup())
    catalog = run(service.list())

    migrated = catalog.workspaces[1]
    assert migrated.name.casefold() != "default workspace"
    assert migrated.directory_name.casefold() != "default"
    assert (managed_root / migrated.directory_name).is_dir()
    assert migrated.mounts[0].root_path == str(external_root.resolve())
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2


@pytest.mark.parametrize(
    ("legacy_name", "preserved"),
    [
        ("developer-\U0001f468\u200d\U0001f4bb", True),
        ("legacy\x7f", False),
        ("unsafe\u202e", False),
    ],
)
def test_v1_migration_preserves_joiners_and_sanitizes_newly_unsafe_names(
    tmp_path: Path,
    legacy_name: str,
    preserved: bool,
) -> None:
    service, data_root, managed_root, external_root = make_service(tmp_path)
    path = data_root / "config" / "workspaces.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "revision": 1,
                "activeWorkspaceId": WORKSPACE_ID,
                "workspaces": [
                    {
                        "id": WORKSPACE_ID,
                        "name": legacy_name,
                        "rootPath": str(external_root.resolve()),
                        "revision": 1,
                        "createdAt": NOW.isoformat(),
                        "updatedAt": NOW.isoformat(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    run(service.startup())
    migrated = run(service.list()).workspaces[1]

    if preserved:
        assert migrated.name == legacy_name
        assert migrated.directory_name == legacy_name
    else:
        assert migrated.name.startswith("workspace-")
        assert migrated.directory_name.startswith("workspace-")
    assert (managed_root / migrated.directory_name).is_dir()
    assert migrated.mounts[0].root_path == str(external_root.resolve())
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2


def test_workspace_store_validates_v2_before_replacing_existing_catalog(
    tmp_path: Path,
) -> None:
    _, data_root, _, external_root = make_service(tmp_path)
    path = data_root / "config" / "workspaces.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "revision": 1,
                "activeWorkspaceId": WORKSPACE_ID,
                "workspaces": [
                    {
                        "id": WORKSPACE_ID,
                        "name": "Legacy",
                        "rootPath": str(external_root.resolve()),
                        "revision": 1,
                        "createdAt": NOW.isoformat(),
                        "updatedAt": NOW.isoformat(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    original = path.read_bytes()
    store = JsonWorkspaceStore(path)
    state = store.get()
    invalid = replace(
        state,
        source_version=2,
        workspaces=(replace(state.workspaces[0], directory_name="default"),),
    )

    with pytest.raises(WorkspaceStoreError):
        store.set(invalid)

    assert path.read_bytes() == original


def test_v1_nested_roots_migrate_as_disabled_mounts(tmp_path: Path) -> None:
    service, data_root, _, external_root = make_service(tmp_path)
    child = external_root / "child"
    child.mkdir()
    path = data_root / "config" / "workspaces.json"
    path.parent.mkdir(parents=True)
    items = []
    for identifier, name, root in (
        (WORKSPACE_ID, "Parent", external_root),
        (SECOND_ID, "Child", child),
    ):
        items.append({
            "id": identifier,
            "name": name,
            "rootPath": str(root.resolve()),
            "revision": 1,
            "createdAt": NOW.isoformat(),
            "updatedAt": NOW.isoformat(),
        })
    path.write_text(json.dumps({
        "version": 1,
        "revision": 2,
        "activeWorkspaceId": WORKSPACE_ID,
        "workspaces": items,
    }), encoding="utf-8")

    run(service.startup())
    catalog = run(service.list())

    assert [item.mounts[0].enabled for item in catalog.workspaces[1:]] == [False, False]
    assert [item.mounts[0].availability.value for item in catalog.workspaces[1:]] == [
        "unavailable", "unavailable"
    ]
    assert [item.mounts[0].unavailable_reason.value for item in catalog.workspaces[1:]] == [
        "overlap", "overlap"
    ]


def test_v1_migration_write_failure_preserves_catalog_and_removes_new_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, data_root, managed_root, external_root = make_service(tmp_path)
    path = data_root / "config" / "workspaces.json"
    path.parent.mkdir(parents=True)
    payload = {
        "version": 1,
        "revision": 1,
        "activeWorkspaceId": WORKSPACE_ID,
        "workspaces": [{
            "id": WORKSPACE_ID,
            "name": "Legacy",
            "rootPath": str(external_root.resolve()),
            "revision": 1,
            "createdAt": NOW.isoformat(),
            "updatedAt": NOW.isoformat(),
        }],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("failure")))

    run(service.startup())

    assert path.read_bytes() == before
    assert not (managed_root / "Legacy").exists()
    assert external_root.is_dir()


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"version":2,"version":2,"revision":0,"activeWorkspaceId":"00000000-0000-4000-8000-000000000000","defaultWorkspace":{},"workspaces":[]}',
        '{"version":3,"revision":0,"activeWorkspaceId":"00000000-0000-4000-8000-000000000000","workspaces":[]}',
    ],
)
def test_store_rejects_malformed_input(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "workspaces.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(WorkspaceStoreError) as raised:
        JsonWorkspaceStore(path).get()

    assert str(raised.value) == "Workspace settings are unavailable."
    assert raised.value.__cause__ is None


def test_atomic_failure_removes_new_empty_root_and_preserves_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, data_root, managed_root, _ = make_service(tmp_path)
    run(service.startup())
    path = data_root / "config" / "workspaces.json"

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("private failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(WorkspaceError) as raised:
        run(service.create(name="Alpha", expected_revision=0))

    assert raised.value.failure is WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE
    assert not (managed_root / "Alpha").exists()
    assert not path.exists()


def test_mount_crud_defaults_read_only_and_blocks_overlap(tmp_path: Path) -> None:
    service, _, managed_root, external_root = make_service(
        tmp_path,
        identifiers=[WORKSPACE_ID, MOUNT_ID],
    )
    run(service.startup())
    created = run(service.create(name="Alpha", expected_revision=0))
    added = run(service.add_mount(
        WORKSPACE_ID,
        alias="Docs",
        root_path=str(external_root),
        access_mode=WorkspaceMountAccess.READ_ONLY,
        enabled=True,
        expected_revision=created.workspaces[1].revision,
    ))

    assert added.mounts[0].access_mode is WorkspaceMountAccess.READ_ONLY
    assert added.mounts[0].enabled is True
    assert added.mounts[0].availability is WorkspaceAvailability.AVAILABLE

    nested = external_root / "nested"
    nested.mkdir()
    with pytest.raises(WorkspaceError) as overlap:
        run(service.add_mount(
            DEFAULT_WORKSPACE_ID,
            alias="Nested",
            root_path=str(nested),
            access_mode=WorkspaceMountAccess.READ_ONLY,
            enabled=True,
            expected_revision=1,
        ))
    assert overlap.value.failure is WorkspaceFailure.OVERLAPPING_ROOT

    with pytest.raises(WorkspaceError) as managed_overlap:
        run(service.add_mount(
            DEFAULT_WORKSPACE_ID,
            alias="Managed",
            root_path=str(managed_root / "Alpha"),
            access_mode=WorkspaceMountAccess.READ_ONLY,
            enabled=True,
            expected_revision=1,
        ))
    assert managed_overlap.value.failure is WorkspaceFailure.OVERLAPPING_ROOT

    updated = run(service.update_mount(
        WORKSPACE_ID,
        added.mounts[0].id,
        alias="Project",
        root_path=str(external_root),
        access_mode=WorkspaceMountAccess.READ_WRITE,
        enabled=False,
        expected_revision=added.revision,
    ))
    assert updated.mounts[0].alias == "Project"
    assert updated.mounts[0].access_mode is WorkspaceMountAccess.READ_WRITE
    assert updated.mounts[0].availability is WorkspaceAvailability.NOT_APPLICABLE

    removed = run(service.delete_mount(
        WORKSPACE_ID,
        updated.mounts[0].id,
        expected_revision=updated.revision,
    ))
    assert removed.mounts == ()
    assert external_root.is_dir()


def test_mount_mutation_is_blocked_while_run_is_active(tmp_path: Path) -> None:
    usage = UsageReader()
    usage.values[DEFAULT_WORKSPACE_ID] = WorkspaceUsage(active_run_count=1)
    service, _, _, external_root = make_service(
        tmp_path, usage=usage, identifiers=[MOUNT_ID]
    )
    run(service.startup())

    with pytest.raises(WorkspaceError) as raised:
        run(service.add_mount(
            DEFAULT_WORKSPACE_ID,
            alias="Docs",
            root_path=str(external_root),
            access_mode=WorkspaceMountAccess.READ_ONLY,
            enabled=True,
            expected_revision=1,
        ))

    assert raised.value.failure is WorkspaceFailure.WORKSPACE_BUSY


def test_workspace_rejects_the_twenty_first_mount(tmp_path: Path) -> None:
    identifiers = [f"{index:08x}-0000-4000-8000-{index:012x}" for index in range(1, 22)]
    service, _, _, _ = make_service(tmp_path, identifiers=identifiers)
    run(service.startup())
    revision = 1
    for index in range(20):
        root = tmp_path / "mounts" / str(index)
        root.mkdir(parents=True)
        item = run(service.add_mount(
            DEFAULT_WORKSPACE_ID,
            alias=f"Mount {index}",
            root_path=str(root),
            access_mode=WorkspaceMountAccess.READ_ONLY,
            enabled=True,
            expected_revision=revision,
        ))
        revision = item.revision
    extra = tmp_path / "mounts" / "extra"
    extra.mkdir()

    with pytest.raises(WorkspaceError) as raised:
        run(service.add_mount(
            DEFAULT_WORKSPACE_ID,
            alias="Extra",
            root_path=str(extra),
            access_mode=WorkspaceMountAccess.READ_ONLY,
            enabled=True,
            expected_revision=revision,
        ))

    assert raised.value.failure is WorkspaceFailure.MOUNT_LIMIT_REACHED


def test_missing_mount_is_reported_without_substituting_a_path(tmp_path: Path) -> None:
    service, _, _, external_root = make_service(tmp_path, identifiers=[MOUNT_ID])
    run(service.startup())
    mounted = run(service.add_mount(
        DEFAULT_WORKSPACE_ID,
        alias="Docs",
        root_path=str(external_root),
        access_mode=WorkspaceMountAccess.READ_ONLY,
        enabled=True,
        expected_revision=1,
    ))
    external_root.rmdir()

    refreshed = run(service.get(DEFAULT_WORKSPACE_ID))

    assert refreshed.mounts[0].id == mounted.mounts[0].id
    assert refreshed.mounts[0].root_path == str(external_root.resolve())
    assert refreshed.mounts[0].availability is WorkspaceAvailability.UNAVAILABLE
    assert refreshed.mounts[0].unavailable_reason.value == "missing"

    disabled = run(service.update_mount(
        DEFAULT_WORKSPACE_ID,
        refreshed.mounts[0].id,
        alias="Docs",
        root_path=refreshed.mounts[0].root_path,
        access_mode=WorkspaceMountAccess.READ_ONLY,
        enabled=False,
        expected_revision=refreshed.revision,
    ))
    assert disabled.mounts[0].enabled is False
    assert disabled.mounts[0].availability is WorkspaceAvailability.NOT_APPLICABLE


def test_delete_preserves_managed_directory_and_returns_to_default(tmp_path: Path) -> None:
    service, _, managed_root, _ = make_service(tmp_path)
    run(service.startup())
    created = run(service.create(name="Keep", expected_revision=0))
    run(service.delete(WORKSPACE_ID, expected_revision=created.workspaces[1].revision))

    catalog = run(service.list())
    assert catalog.active_workspace_id == DEFAULT_WORKSPACE_ID
    assert len(catalog.workspaces) == 1
    assert (managed_root / "Keep").is_dir()


def test_delete_still_requires_empty_workspace(tmp_path: Path) -> None:
    usage = UsageReader()
    service, _, _, _ = make_service(tmp_path, usage=usage)
    run(service.startup())
    created = run(service.create(name="Alpha", expected_revision=0))
    usage.values[WORKSPACE_ID] = WorkspaceUsage(conversation_count=1)

    with pytest.raises(WorkspaceError) as raised:
        run(service.delete(WORKSPACE_ID, expected_revision=created.workspaces[1].revision))

    assert raised.value.failure is WorkspaceFailure.WORKSPACE_NOT_EMPTY


def test_windows_reparse_attribute_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _, external_root = make_service(tmp_path, identifiers=[MOUNT_ID])
    run(service.startup())
    fake_path = SimpleNamespace(lstat=lambda: SimpleNamespace(st_file_attributes=0x400))
    original_os_name = workspace_policy.os.name
    monkeypatch.setattr(workspace_policy.os, "name", "nt")
    assert WorkspaceRootPolicy._is_reparse_point(fake_path) is True
    monkeypatch.setattr(workspace_policy.os, "name", original_os_name)
    monkeypatch.setattr(service._root_policy, "_is_reparse_point", lambda _path: True)

    with pytest.raises(WorkspaceError) as reparse:
        run(service.add_mount(
            DEFAULT_WORKSPACE_ID,
            alias="Unsafe",
            root_path=str(external_root),
            access_mode=WorkspaceMountAccess.READ_ONLY,
            enabled=True,
            expected_revision=1,
        ))
    assert reparse.value.failure is WorkspaceFailure.UNSAFE_ROOT


def test_api_managed_create_import_mount_and_strict_delete(tmp_path: Path) -> None:
    service, _, managed_root, external_root = make_service(
        tmp_path,
        identifiers=[WORKSPACE_ID, MOUNT_ID],
    )
    run(service.startup())
    (managed_root / "Existing").mkdir()
    with TestClient(create_app(workspaces=service)) as client:
        initial = client.get("/api/workspaces")
        candidates = client.get("/api/workspaces/import-candidates?limit=50")
        created = client.post("/api/workspaces", json={"name": "Alpha", "expectedRevision": 0})
        mounted = client.post(
            f"/api/workspaces/{WORKSPACE_ID}/mounts",
            json={
                "alias": "Docs",
                "rootPath": str(external_root),
                "accessMode": "read_only",
                "enabled": True,
                "expectedRevision": 1,
            },
        )
        invalid_deletes = [
            client.delete(f"/api/workspaces/{WORKSPACE_ID}"),
            client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=2&unexpected=1"),
            client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=0"),
        ]
        mount_removed = client.delete(
            f"/api/workspaces/{WORKSPACE_ID}/mounts/{MOUNT_ID}?expectedRevision=2"
        )
        removed = client.delete(f"/api/workspaces/{WORKSPACE_ID}?expectedRevision=3")

    assert initial.status_code == 200
    assert initial.json()["workspaces"][0]["kind"] == "default"
    assert candidates.json()["candidates"][0]["directoryName"] == "Existing"
    assert created.status_code == 201
    assert created.json()["workspaces"][1]["rootPath"] == str((managed_root / "Alpha").resolve())
    assert mounted.status_code == 201
    assert mounted.json()["mounts"][0]["accessMode"] == "read_only"
    assert all(item.status_code == 400 for item in invalid_deletes)
    assert mount_removed.status_code == 200
    assert removed.status_code == 204
    assert (managed_root / "Alpha").is_dir()


def test_workspace_api_obeys_same_origin_protection(tmp_path: Path) -> None:
    service, _, _, _ = make_service(tmp_path)
    run(service.startup())
    app = create_app(workspaces=service, enforce_local_security=True)
    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.post(
            "/api/workspaces",
            headers={"Origin": "http://evil.example"},
            json={"name": "Alpha", "expectedRevision": 0},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_app_paths_owns_managed_and_sensitive_workspace_locations(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    assert paths.workspace_settings_file == paths.home / "config" / "workspaces.json"
    assert paths.managed_workspaces_dir == tmp_path / "OpenSprite" / "workspace"


def test_system_runtime_exposes_available_default_workspace(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    app = create_system_app(app_paths=paths, enforce_authentication=False)

    with TestClient(app, base_url="http://localhost:8765") as client:
        response = client.get("/api/workspaces")

    assert response.status_code == 200
    assert response.json()["activeWorkspaceId"] == DEFAULT_WORKSPACE_ID
    assert response.json()["workspaces"][0]["kind"] == "default"
    assert response.json()["workspaces"][0]["availability"] == "available"
    assert paths.managed_workspaces_dir.joinpath("default").is_dir()
    assert not paths.workspace_settings_file.exists()
