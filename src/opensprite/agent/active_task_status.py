"""Shared parsing for rendered ACTIVE_TASK status blocks."""

from __future__ import annotations

import re


_ACTIVE_STATUS_RE = re.compile(r"^- Status:\s*(?P<status>.+)$", re.MULTILINE)
_CURRENT_TASK_STATUSES = frozenset({"active", "blocked", "waiting_user"})


def active_task_status(active_task_snapshot: str | None) -> str:
    """Return the normalized status from a rendered ACTIVE_TASK block."""
    match = _ACTIVE_STATUS_RE.search(str(active_task_snapshot or ""))
    if not match:
        return "inactive"
    return match.group("status").strip().lower() or "inactive"


def has_current_active_task(active_task_snapshot: str | None) -> bool:
    """Return whether the rendered ACTIVE_TASK block represents current work."""
    return active_task_status(active_task_snapshot) in _CURRENT_TASK_STATUSES

