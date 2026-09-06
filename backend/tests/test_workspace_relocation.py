"""Real filesystem relocation, restart and data-boundary regressions."""
from asyncio import run
import json
from pathlib import Path

import pytest

from opensprite_backend.workspaces import WorkspaceAvailability
from opensprite_backend.workspaces.relocation import WorkspaceRelocator, WorkspaceRelocationError
from test_workspaces import make_service


def legacy_service(tmp_path):
    service, data, target, _ = make_service(tmp_path)
    run(service.startup())
    run(service.create(name="Alpha", expected_revision=0))
    source = tmp_path / "OpenSprite" / "workspace"
    source.parent.mkdir()
    target.rename(source)
    catalog = data / "config" / "workspaces.json"
    raw = json.loads(catalog.read_text())
    raw["version"] = 2
    catalog.write_text(json.dumps(raw), encoding="utf-8")
    service._relocator = WorkspaceRelocator(source, target, data / "config" / "workspace-relocation.json")
    return service, source, target, catalog


def test_relocation_copies_contents_preserves_source_and_increments_revision(tmp_path):
    service, source, target, catalog = legacy_service(tmp_path)
    (source / "Alpha" / "中文.txt").write_text("original", encoding="utf-8")
    (source / "default" / "nested").mkdir()
    run(service.startup())
    assert (target / "Alpha" / "中文.txt").read_text(encoding="utf-8") == "original"
    assert (source / "Alpha" / "中文.txt").exists()
    assert (target / "default" / "nested").is_dir()
    raw = json.loads(catalog.read_text())
    assert raw["version"] == 3
    assert raw["revision"] == 2 and raw["workspaces"][0]["revision"] == 2
    run(service.startup())
    assert json.loads(catalog.read_text()) == raw
    assert all(w.availability is WorkspaceAvailability.AVAILABLE for w in run(service.list()).workspaces)


def test_existing_target_is_not_merged_or_adopted(tmp_path):
    service, source, target, catalog = legacy_service(tmp_path)
    (target / "Alpha").mkdir(parents=True)
    (target / "Alpha" / "keep").write_text("keep")
    run(service.startup())
    assert json.loads(catalog.read_text())["version"] == 2
    assert (target / "Alpha" / "keep").read_text() == "keep"
    assert source.joinpath("Alpha").is_dir()
    assert all(w.availability is WorkspaceAvailability.UNAVAILABLE for w in run(service.list()).workspaces)


def test_catalog_write_failure_can_resume_without_recopy(tmp_path, monkeypatch):
    service, source, target, catalog = legacy_service(tmp_path)
    original = service._store.set
    from opensprite_backend.workspaces import WorkspaceStoreError
    def fail(_):
        raise WorkspaceStoreError
    monkeypatch.setattr(service._store, "set", fail)
    run(service.startup())
    assert json.loads(catalog.read_text())["version"] == 2
    assert target.joinpath("Alpha").is_dir()
    monkeypatch.setattr(service._store, "set", original)
    run(service.startup())
    assert json.loads(catalog.read_text())["version"] == 3
    assert source.joinpath("Alpha").is_dir()


def test_changed_source_during_copy_does_not_commit(tmp_path, monkeypatch):
    service, source, target, catalog = legacy_service(tmp_path)
    import opensprite_backend.workspaces.relocation as module
    copy = module.shutil.copytree
    def changed(src, dst, **kwargs):
        result = copy(src, dst, **kwargs)
        Path(src, "changed").write_text("later")
        return result
    monkeypatch.setattr(module.shutil, "copytree", changed)
    run(service.startup())
    assert json.loads(catalog.read_text())["version"] == 2
    assert not target.joinpath("default").exists()


def test_external_mount_policy_still_denies_data_and_managed_roots(tmp_path):
    service, data, target, _ = make_service(tmp_path)
    run(service.startup())
    from opensprite_backend.workspaces.policy import UnsafeWorkspaceRoot
    for path in (data, target, target / "default"):
        with pytest.raises(UnsafeWorkspaceRoot):
            service._root_policy.validate_new_root(str(path))
    assert run(service.list()).workspaces[0].availability is WorkspaceAvailability.AVAILABLE


def test_missing_legacy_root_is_not_replaced_with_empty_directory(tmp_path):
    service, source, target, catalog = legacy_service(tmp_path)
    source.joinpath("Alpha").rmdir()
    run(service.startup())
    assert not target.joinpath("Alpha").exists()
    assert json.loads(catalog.read_text())["version"] == 3
    assert run(service.list()).workspaces[1].availability is WorkspaceAvailability.UNAVAILABLE


def test_failed_copy_keeps_source_and_can_retry(tmp_path, monkeypatch):
    service, source, target, catalog = legacy_service(tmp_path)
    import opensprite_backend.workspaces.relocation as module
    copy = module.shutil.copytree
    def denied(*args, **kwargs):
        raise PermissionError
    monkeypatch.setattr(module.shutil, "copytree", denied)
    run(service.startup())
    assert json.loads(catalog.read_text())["version"] == 2
    monkeypatch.setattr(module.shutil, "copytree", copy)
    run(service.startup())
    assert json.loads(catalog.read_text())["version"] == 3


def test_symlink_source_is_not_followed(tmp_path):
    source, target = tmp_path / "old", tmp_path / "new"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        source.joinpath("default").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not grant symlink creation")
    with pytest.raises(WorkspaceRelocationError):
        WorkspaceRelocator(source, target, tmp_path / "journal.json").relocate(("default",))
    assert not target.joinpath("default").exists()


def test_managed_parent_reparse_attribute_is_rejected(tmp_path, monkeypatch):
    service, _, target, _ = make_service(tmp_path)
    run(service.startup())
    monkeypatch.setattr(service._root_policy, "_is_reparse_point", lambda path: path == target)
    assert run(service.list()).workspaces[0].unavailable_reason.value == "unsafe"


def test_failed_relocation_blocks_catalog_mutations(tmp_path):
    service, source, target, catalog = legacy_service(tmp_path)
    (target / "Alpha").mkdir(parents=True)
    run(service.startup())
    from opensprite_backend.workspaces import WorkspaceError
    original = catalog.read_bytes()
    with pytest.raises(WorkspaceError):
        run(service.create(name="Other", expected_revision=1))
    assert catalog.read_bytes() == original
    assert not target.joinpath("Other").exists()
