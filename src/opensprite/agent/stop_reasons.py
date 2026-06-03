"""Shared execution stop reason policy helpers."""

from __future__ import annotations

MAX_TOOL_ITERATIONS_STOP_REASON = "max_tool_iterations"


def is_max_tool_iterations_stop_reason(stop_reason: str | None) -> bool:
    return str(stop_reason or "").strip() == MAX_TOOL_ITERATIONS_STOP_REASON
