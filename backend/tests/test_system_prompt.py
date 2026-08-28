"""Dynamic system-prompt rendering and full-log persistence tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

import pytest

import opensprite_backend.system_prompt as system_prompt_module
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.general_settings import GeneralSettingsStoreError
from opensprite_backend.models import GeneralSettings
from opensprite_backend.system_prompt import (
    SystemPromptLogError,
    create_system_prompt_provider,
)


class StubGeneralSettings:
    def __init__(self, settings: GeneralSettings) -> None:
        self.settings = settings

    async def get(self) -> GeneralSettings:
        return self.settings


class UnavailableGeneralSettings:
    async def get(self) -> GeneralSettings:
        raise GeneralSettingsStoreError


def fixed_clock() -> datetime:
    return datetime(2026, 8, 28, 8, 30, tzinfo=timezone.utc)


def test_dynamic_prompt_uses_confirmed_locale_timezone_and_writes_full_log(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    run_id = str(uuid4())
    provider = create_system_prompt_provider(
        paths,
        StubGeneralSettings(
            GeneralSettings(locale="zh-TW", timeZone="Asia/Taipei")
        ),
        clock=fixed_clock,
    )

    assert not paths.home.exists()

    prompt = asyncio.run(provider.build(run_id=run_id))

    assert "# Role" in prompt
    assert "# Task" in prompt
    assert "# Constraints" in prompt
    assert "# Output" in prompt
    assert "Traditional Chinese (Taiwan) [zh-TW]" in prompt
    assert "2026-08-28T16:30:00+08:00" in prompt
    assert "Asia/Taipei" in prompt
    assert run_id not in prompt
    log_path = paths.system_prompt_logs_dir / "2026-08-28" / f"{run_id}.md"
    assert log_path.is_file()
    logged = log_path.read_text(encoding="utf-8")
    assert prompt in logged
    assert f"Run ID: {run_id}" in logged
    assert "Prompt version: 1" in logged
    assert "Settings fallback: false" in logged
    assert "SHA-256:" in logged
    assert sorted(path for path in paths.home.rglob("*") if path.is_file()) == [
        log_path
    ]


def test_unavailable_general_settings_use_neutral_utc_fallback_and_log_it(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    run_id = str(uuid4())
    provider = create_system_prompt_provider(
        paths,
        UnavailableGeneralSettings(),
        clock=fixed_clock,
    )

    prompt = asyncio.run(provider.build(run_id=run_id))

    assert "follow the user's language" in prompt
    assert "2026-08-28T08:30:00+00:00" in prompt
    assert "UTC" in prompt
    logged = (
        paths.system_prompt_logs_dir / "2026-08-28" / f"{run_id}.md"
    ).read_text(encoding="utf-8")
    assert "Settings fallback: true" in logged


def test_prompt_log_is_create_only_and_preserves_the_first_complete_entry(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    run_id = str(uuid4())
    provider = create_system_prompt_provider(
        paths,
        StubGeneralSettings(GeneralSettings(locale="en", timeZone="UTC")),
        clock=fixed_clock,
    )
    asyncio.run(provider.build(run_id=run_id))
    log_path = paths.system_prompt_logs_dir / "2026-08-28" / f"{run_id}.md"
    original = log_path.read_bytes()

    with pytest.raises(SystemPromptLogError):
        asyncio.run(provider.build(run_id=run_id))

    assert log_path.read_bytes() == original
    assert not list(log_path.parent.glob("*.tmp"))


def test_invalid_run_id_is_rejected_without_creating_the_data_root(
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    provider = create_system_prompt_provider(
        paths,
        StubGeneralSettings(GeneralSettings(locale="en", timeZone="UTC")),
        clock=fixed_clock,
    )

    with pytest.raises(SystemPromptLogError):
        asyncio.run(provider.build(run_id="../outside"))

    assert not paths.home.exists()


def test_failed_log_fsync_removes_partial_prompt_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    run_id = str(uuid4())
    provider = create_system_prompt_provider(
        paths,
        StubGeneralSettings(GeneralSettings(locale="en", timeZone="UTC")),
        clock=fixed_clock,
    )

    def fail_fsync(_descriptor: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr(
        system_prompt_module.os,
        "fsync",
        fail_fsync,
    )

    with pytest.raises(SystemPromptLogError):
        asyncio.run(provider.build(run_id=run_id))

    assert not list(paths.system_prompt_logs_dir.rglob("*.md"))


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission contract")
def test_prompt_log_directories_and_file_are_owner_only(tmp_path: Path) -> None:
    paths = build_app_paths(tmp_path / ".opensprite")
    run_id = str(uuid4())
    provider = create_system_prompt_provider(
        paths,
        StubGeneralSettings(GeneralSettings(locale="ja", timeZone="UTC")),
        clock=fixed_clock,
    )

    asyncio.run(provider.build(run_id=run_id))

    log_path = paths.system_prompt_logs_dir / "2026-08-28" / f"{run_id}.md"
    assert log_path.parent.stat().st_mode & 0o777 == 0o700
    assert log_path.stat().st_mode & 0o777 == 0o600
