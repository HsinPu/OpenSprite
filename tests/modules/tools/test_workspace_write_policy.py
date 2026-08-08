"""Workspace write-protection policy behavior."""

from pathlib import Path

from opensprite.modules.tools.workspace_write_policy import evaluate_workspace_write_protection


def test_blocks_default_and_runtime_config_paths(tmp_path):
    default_config = evaluate_workspace_write_protection(tmp_path / "OpenSprite.JSON")
    runtime_config = evaluate_workspace_write_protection(
        tmp_path / "channels.json",
        blocked_paths_resolver=lambda: frozenset({(tmp_path / "channels.json").resolve()}),
    )

    assert default_config is not None
    assert default_config.category == "protected_config"
    assert "configuration files" in default_config.message.lower()
    assert runtime_config is not None
    assert runtime_config.category == "protected_config"


def test_blocks_sensitive_files_and_directories_under_home_case_insensitively(tmp_path):
    home = tmp_path / "home"
    key_file = evaluate_workspace_write_protection(home / ".SSH" / "ID_ED25519", home_path=home)
    cloud_credentials = evaluate_workspace_write_protection(home / ".AWS" / "credentials", home_path=home)

    assert key_file is not None
    assert key_file.category == "sensitive_user_config"
    assert "sensitive user configuration" in key_file.message.lower()
    assert cloud_credentials is not None
    assert cloud_credentials.category == "sensitive_user_config"


def test_allows_unrelated_paths_and_does_not_require_runtime_config(tmp_path):
    protection = evaluate_workspace_write_protection(tmp_path / "notes.txt", home_path=tmp_path / "home")

    assert protection is None
