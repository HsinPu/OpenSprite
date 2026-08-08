"""Formatting helpers for user-facing scheduling messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from ...config import CronMessagesConfig
from .types import CronSchedule


def format_cron_timestamp(ms: int, tz_name: str) -> str:
    from zoneinfo import ZoneInfo

    dt = datetime.fromtimestamp(ms / 1000, tz=ZoneInfo(tz_name))
    return f"{dt.isoformat()} ({tz_name})"


def format_cron_timing(schedule: CronSchedule, default_timezone: str = "UTC") -> str:
    if schedule.kind == "cron":
        tz = f" ({schedule.tz})" if schedule.tz else ""
        return f"cron: {schedule.expr}{tz}"
    if schedule.kind == "every" and schedule.every_ms:
        if schedule.every_ms % 3_600_000 == 0:
            return f"every {schedule.every_ms // 3_600_000}h"
        if schedule.every_ms % 60_000 == 0:
            return f"every {schedule.every_ms // 60_000}m"
        if schedule.every_ms % 1000 == 0:
            return f"every {schedule.every_ms // 1000}s"
        return f"every {schedule.every_ms}ms"
    if schedule.kind == "at" and schedule.at_ms:
        return f"at {format_cron_timestamp(schedule.at_ms, schedule.tz or default_timezone)}"
    return schedule.kind


def render_cron_jobs(
    jobs: Iterable[Any],
    messages: CronMessagesConfig,
    *,
    default_timezone: str = "UTC",
) -> str:
    jobs_list = list(jobs)
    if not jobs_list:
        return messages.no_jobs

    lines: list[str] = []
    for job in jobs_list:
        line = messages.job_list_item.format(
            name=job.name,
            job_id=job.id,
            timing=format_cron_timing(job.schedule, default_timezone),
        )
        if job.state.next_run_at_ms:
            line += "\n  " + messages.next_run_label.format(
                timestamp=format_cron_timestamp(job.state.next_run_at_ms, job.schedule.tz or default_timezone)
            )
        lines.append(line)
    return messages.jobs_header + "\n" + "\n".join(lines)
