"""Cron command helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Callable

import typer

from ..context.paths import get_session_workspace
from ..cron import CronSchedule, CronService
from ..cron.presentation import render_cron_jobs


def get_cron_service(session: str, *, resolve_workspace_root: Callable[[], Path]) -> CronService:
    """Open the cron service store for a session without starting a timer loop."""
    workspace = get_session_workspace(session, workspace_root=resolve_workspace_root())
    return CronService(workspace / "cron" / "jobs.json", session_id=session)


def build_cli_schedule(
    *,
    every_seconds: int | None,
    cron_expr: str | None,
    tz: str | None,
    at: str | None,
    default_timezone: str = "UTC",
) -> tuple[CronSchedule, bool]:
    """Build a CronSchedule from CLI arguments."""
    provided = [every_seconds is not None, bool(cron_expr), bool(at)]
    if sum(provided) != 1:
        raise ValueError("provide exactly one of --every-seconds, --cron-expr, or --at")
    if tz and not cron_expr:
        raise ValueError("--tz can only be used with --cron-expr")
    if every_seconds is not None:
        if every_seconds <= 0:
            raise ValueError("--every-seconds must be greater than 0")
        return CronSchedule(kind="every", every_ms=every_seconds * 1000), False
    if cron_expr:
        return CronSchedule(kind="cron", expr=cron_expr, tz=tz or default_timezone), False
    try:
        dt = datetime.fromisoformat(at or "")
    except ValueError as exc:
        raise ValueError("--at must use ISO format like 2026-04-10T09:00:00") from exc
    if dt.tzinfo is None:
        from zoneinfo import ZoneInfo

        dt = dt.replace(tzinfo=ZoneInfo(default_timezone))
    return CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000)), True


def load_cli_cron_messages(config: str | None, *, resolve_config_path: Callable[[str | None], Path]):
    from ..config import Config, CronMessagesConfig

    config_path = resolve_config_path(config)
    if not config_path.exists():
        return CronMessagesConfig()
    try:
        return Config.from_json(config_path).messages.cron
    except Exception:
        return CronMessagesConfig()


def render_cron_jobs_text(service: CronService, default_timezone: str = "UTC", *, messages=None) -> str:
    """Render the stored jobs for CLI list output."""
    return render_cron_jobs(service.list_jobs(include_disabled=True), messages, default_timezone=default_timezone)


def cron_list_command(*, session: str, config: str | None, get_cron_service: Callable[[str], CronService], load_cli_cron_messages: Callable[[str | None], object], render_cron_jobs_text: Callable[..., str]) -> None:
    service = get_cron_service(session)
    messages = load_cli_cron_messages(config)
    typer.echo(render_cron_jobs_text(service, messages=messages))


def cron_add_command(*, session: str, message: str, name: str | None, every_seconds: int | None, cron_expr: str | None, tz: str | None, at: str | None, deliver: bool, config: str | None, get_cron_service: Callable[[str], CronService], build_cli_schedule: Callable[..., tuple[CronSchedule, bool]], load_cli_cron_messages: Callable[[str | None], object], handle_cron_error: Callable[[Exception | str], None]) -> None:
    messages = load_cli_cron_messages(config)
    try:
        schedule, delete_after = build_cli_schedule(every_seconds=every_seconds, cron_expr=cron_expr, tz=tz, at=at)
        service = get_cron_service(session)
        if ":" in session:
            channel, external_chat_id = session.split(":", 1)
        else:
            channel, external_chat_id = "default", session
        job = service.add_job(
            name=name or message[:30],
            schedule=schedule,
            message=message,
            deliver=deliver,
            channel=channel,
            external_chat_id=external_chat_id,
            delete_after_run=delete_after,
        )
    except ValueError as exc:
        handle_cron_error(exc)
    typer.echo(messages.created_job.format(name=job.name, job_id=job.id))


def cron_remove_command(*, session: str, job_id: str, config: str | None, get_cron_service: Callable[[str], CronService], load_cli_cron_messages: Callable[[str | None], object], handle_cron_error: Callable[[Exception | str], None]) -> None:
    messages = load_cli_cron_messages(config)
    service = get_cron_service(session)
    if not service.remove_job(job_id):
        handle_cron_error(messages.job_not_found.format(job_id=job_id))
    typer.echo(messages.removed_job.format(job_id=job_id))


def cron_pause_command(*, session: str, job_id: str, config: str | None, get_cron_service: Callable[[str], CronService], load_cli_cron_messages: Callable[[str | None], object], handle_cron_error: Callable[[Exception | str], None]) -> None:
    messages = load_cli_cron_messages(config)
    service = get_cron_service(session)
    if not service.pause_job(job_id):
        handle_cron_error(messages.job_not_found_or_paused.format(job_id=job_id))
    typer.echo(messages.paused_job.format(job_id=job_id))


def cron_enable_command(*, session: str, job_id: str, config: str | None, get_cron_service: Callable[[str], CronService], load_cli_cron_messages: Callable[[str | None], object], handle_cron_error: Callable[[Exception | str], None]) -> None:
    messages = load_cli_cron_messages(config)
    service = get_cron_service(session)
    if not service.enable_job(job_id):
        handle_cron_error(messages.job_not_found_or_enabled.format(job_id=job_id))
    typer.echo(messages.enabled_job.format(job_id=job_id))


def cron_run_command(*, session: str, job_id: str, config: str | None, get_cron_service: Callable[[str], CronService], load_cli_cron_messages: Callable[[str | None], object], handle_cron_error: Callable[[Exception | str], None]) -> None:
    messages = load_cli_cron_messages(config)
    service = get_cron_service(session)
    if not asyncio.run(service.run_job(job_id)):
        handle_cron_error(messages.job_not_found.format(job_id=job_id))
    typer.echo(messages.ran_job.format(job_id=job_id))
