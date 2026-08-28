"""Path-contract and ownership guards for local OpenSprite data."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from opensprite_backend.app_paths import AppPaths, build_app_paths
from opensprite_backend.runtime import create_system_app


def test_build_app_paths_maps_the_complete_layout_without_creating_it(
    tmp_path: Path,
) -> None:
    home = tmp_path / "profile" / ".opensprite"

    paths = build_app_paths(home)

    assert paths == AppPaths(home=home.resolve(strict=False))
    assert paths.credential_file == home / "auth.json"
    assert paths.credential_key_file == home / "config" / "credential.key"
    assert paths.config_dir == home / "config"
    assert paths.settings_file == home / "config" / "settings.json"
    assert paths.general_settings_file == home / "config" / "general.json"
    assert paths.data_dir == home / "data"
    assert paths.database_file == home / "data" / "opensprite.db"
    assert paths.state_dir == home / "state"
    assert paths.provider_state_file == home / "state" / "providers.json"
    assert paths.provider_transaction_file == (
        home / "state" / "provider-transaction.json"
    )
    assert paths.conversations_dir == home / "conversations"
    assert paths.logs_dir == home / "logs"
    assert paths.cache_dir == home / "cache"
    assert not home.exists()


def test_default_root_is_hidden_opensprite_under_the_user_profile(
    monkeypatch,
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: profile))

    paths = build_app_paths()

    assert paths.home == (profile / ".opensprite").resolve(strict=False)
    assert not paths.home.exists()


def test_system_app_lifespan_does_not_create_the_data_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: profile))
    app = create_system_app()

    with TestClient(app, base_url="http://127.0.0.1:8765"):
        assert not (profile / ".opensprite").exists()

    assert not (profile / ".opensprite").exists()


def test_only_app_paths_may_own_the_local_data_root() -> None:
    package_root = Path(__file__).parents[1] / "src" / "opensprite_backend"
    removed_path_dependency = "platform" + "dirs"
    violations: list[str] = []

    for source_path in package_root.rglob("*.py"):
        if source_path.name == "app_paths.py":
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == ".opensprite":
                violations.append(f"{source_path}: .opensprite")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "home"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "Path"
            ):
                violations.append(f"{source_path}: Path.home()")
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == removed_path_dependency
            ):
                violations.append(f"{source_path}: {removed_path_dependency}")
            if isinstance(node, ast.Import) and any(
                alias.name == removed_path_dependency for alias in node.names
            ):
                violations.append(f"{source_path}: {removed_path_dependency}")

    assert violations == []
