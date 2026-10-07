"""Real filesystem cache boundaries, atomic import and removal scope."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from uuid import uuid4

import pytest

from execution_package_test_support import FILE_NAME, paths, wheel
from opensprite_backend.execution_plugins.inspection import inspect_wheel
from opensprite_backend.execution_plugins.models import ExecutionPackageError
from opensprite_backend.execution_plugins.store import ExecutionPackageStore


def test_list_is_lazy_and_identical_concurrent_imports_have_one_uuid(tmp_path):
    data = wheel()
    inspection = inspect_wheel(data, FILE_NAME)
    app_paths = paths(tmp_path)
    store = ExecutionPackageStore(app_paths)
    assert store.list() == []
    assert not app_paths.home.exists()
    with ThreadPoolExecutor(max_workers=4) as pool:
        saved = list(pool.map(lambda _: store.save(inspection, data), range(4)))
    assert len({item.id for item in saved}) == 1
    assert len(store.list()) == 1
    assert store.get(saved[0].id)[1] == data


def test_failed_publish_preserves_existing_cache_and_cleans_owned_staging(tmp_path, monkeypatch):
    store = ExecutionPackageStore(paths(tmp_path))
    data = wheel()
    before = store.save(inspect_wheel(data, FILE_NAME), data)
    original = os.replace
    def fail_publish(source, destination):
        if str(source).split(os.sep)[-1].startswith(".incoming-"):
            raise OSError("PRIVATE CACHE PATH")
        return original(source, destination)
    monkeypatch.setattr(os, "replace", fail_publish)
    updated = wheel(changes={"stage2_fixture_plugin/note.txt": b"second package"})
    with pytest.raises(ExecutionPackageError, match="packages_store_unavailable") as caught:
        store.save(inspect_wheel(updated, FILE_NAME), updated)
    assert "PRIVATE" not in str(caught.value)
    assert [item.id for item in store.list()] == [before.id]
    assert [item.name for item in paths(tmp_path).execution_plugin_packages_dir.iterdir()] == [before.id]


@pytest.mark.parametrize("corruption", ["wheel", "manifest", "foreign-file", "unknown-directory", "duplicate-id"])
def test_cache_corruption_fails_closed_for_get_list(tmp_path, corruption):
    store = ExecutionPackageStore(paths(tmp_path))
    data = wheel()
    stored = store.save(inspect_wheel(data, FILE_NAME), data)
    folder = paths(tmp_path).execution_plugin_packages_dir / stored.id
    if corruption == "wheel":
        (folder / FILE_NAME).write_bytes(b"corrupt")
    elif corruption == "manifest":
        (folder / "manifest.json").write_text('{"schemaVersion":1,"schemaVersion":1}')
    elif corruption == "foreign-file":
        (folder / "unexpected").write_text("do not silently remove")
    elif corruption == "unknown-directory":
        (folder.parent / "not-an-id").mkdir()
    else:
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["id"] = str(uuid4())
        (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ExecutionPackageError, match="packages_store_unavailable"):
        store.list()


def test_delete_removes_only_imported_cache_not_settings_or_installed_files(tmp_path):
    app_paths = paths(tmp_path)
    store = ExecutionPackageStore(app_paths)
    data = wheel()
    stored = store.save(inspect_wheel(data, FILE_NAME), data)
    installed = tmp_path / "site-packages" / "plugin.py"
    installed.parent.mkdir()
    installed.write_text("installed")
    settings = app_paths.home / "config" / "execution.json"
    settings.parent.mkdir()
    settings.write_text('{"loopId":"fixture_loop","policyId":"standard"}')
    store.delete(stored.id)
    assert store.list() == []
    assert installed.read_text() == "installed"
    assert "fixture_loop" in settings.read_text()


def test_cache_symlink_cannot_escape_app_paths_root(tmp_path):
    app_paths = paths(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "preserve.txt"
    sentinel.write_text("preserve")
    app_paths.execution_plugin_packages_dir.parent.mkdir(parents=True)
    try:
        app_paths.execution_plugin_packages_dir.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS account cannot create symlinks")
    store = ExecutionPackageStore(app_paths)
    for operation in (store.list, lambda: store.delete(str(uuid4()))):
        with pytest.raises(ExecutionPackageError, match="packages_store_unavailable"):
            operation()
    assert sentinel.read_text() == "preserve"


def test_interrupted_save_or_removal_does_not_hide_unrelated_packages(tmp_path, monkeypatch):
    app_paths = paths(tmp_path)
    store = ExecutionPackageStore(app_paths)
    data = wheel()
    first = store.save(inspect_wheel(data, FILE_NAME), data)
    other_data = wheel(changes={"stage2_fixture_plugin/note.txt": b"unrelated cached wheel"})
    second = store.save(inspect_wheel(other_data, FILE_NAME), other_data)
    orphan = app_paths.execution_plugin_packages_dir / (".incoming-" + str(uuid4()))
    orphan.mkdir()
    (orphan / "manifest.json").write_text("incomplete transaction")
    original = type(orphan).unlink
    def fail_removal(path, *args, **kwargs):
        if path.parent.name == ".removing-" + first.id:
            raise OSError("interrupted removal")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(type(orphan), "unlink", fail_removal)
    with pytest.raises(ExecutionPackageError, match="packages_store_unavailable"):
        store.delete(first.id)
    restarted = ExecutionPackageStore(app_paths)
    assert [item.id for item in restarted.list()] == [second.id]
    assert orphan.exists()
    assert (app_paths.execution_plugin_packages_dir / (".removing-" + first.id)).exists()


def test_inactive_cache_transactions_count_toward_import_bound(tmp_path):
    from opensprite_backend.execution_plugins.models import MAX_PACKAGES
    app_paths = paths(tmp_path)
    app_paths.execution_plugin_packages_dir.mkdir(parents=True)
    for _ in range(MAX_PACKAGES):
        (app_paths.execution_plugin_packages_dir / (".incoming-" + str(uuid4()))).mkdir()
    store = ExecutionPackageStore(app_paths)
    assert store.list() == []
    data = wheel()
    with pytest.raises(ExecutionPackageError, match="package_too_large"):
        store.save(inspect_wheel(data, FILE_NAME), data)


@pytest.mark.parametrize("member", ["manifest.json", FILE_NAME])
def test_nonregular_cache_member_is_rejected_before_opening(tmp_path, member):
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX FIFO guard")
    app_paths = paths(tmp_path)
    store = ExecutionPackageStore(app_paths)
    data = wheel()
    saved = store.save(inspect_wheel(data, FILE_NAME), data)
    target = app_paths.execution_plugin_packages_dir / saved.id / member
    target.unlink()
    os.mkfifo(target)
    with pytest.raises(ExecutionPackageError, match="packages_store_unavailable"):
        store.list()
