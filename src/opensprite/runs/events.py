"""Shared run trace event type markers."""

from __future__ import annotations

RUN_PART_DELTA_EVENT = "run_part_delta"
MESSAGE_PART_DELTA_EVENT = "message_part_delta"
TOOL_STARTED_EVENT = "tool_started"
TOOL_RESULT_EVENT = "tool_result"

TEXT_DELTA_EVENTS = frozenset({RUN_PART_DELTA_EVENT, MESSAGE_PART_DELTA_EVENT})
TOOL_LIFECYCLE_EVENTS = frozenset({TOOL_STARTED_EVENT, TOOL_RESULT_EVENT})
