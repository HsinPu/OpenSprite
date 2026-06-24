"""Helpers for user-turn directives encoded in message metadata."""

from __future__ import annotations

from typing import Any

from .completion_gate import (
    COMPLETION_RESULT_ACTIVE_TASK_DETAIL_FIELD,
    COMPLETION_RESULT_FOLLOW_UP_PROMPT_TYPE_FIELD,
    COMPLETION_RESULT_FOLLOW_UP_STEP_ID_FIELD,
    COMPLETION_RESULT_FOLLOW_UP_STEP_LABEL_FIELD,
    COMPLETION_RESULT_FOLLOW_UP_WORKFLOW_FIELD,
    COMPLETION_RESULT_VERIFICATION_ACTION_FIELD,
    COMPLETION_RESULT_VERIFICATION_PATH_FIELD,
    COMPLETION_RESULT_VERIFICATION_PYTEST_ARGS_FIELD,
)
from .turn_input import (
    metadata_requests_direct_verification,
    metadata_requests_follow_up_resume,
    metadata_text,
)


def extract_follow_up_resume_request(metadata: dict[str, Any] | None) -> dict[str, str] | None:
    payload = dict(metadata or {}) if isinstance(metadata, dict) else {}
    if not metadata_requests_follow_up_resume(payload):
        return None
    workflow = metadata_text(payload, COMPLETION_RESULT_FOLLOW_UP_WORKFLOW_FIELD)
    start_step = metadata_text(payload, COMPLETION_RESULT_FOLLOW_UP_STEP_ID_FIELD)
    if not workflow or not start_step:
        return None
    return {
        "workflow": workflow,
        "start_step": start_step,
        "step_label": metadata_text(payload, COMPLETION_RESULT_FOLLOW_UP_STEP_LABEL_FIELD, start_step) or start_step,
        "prompt_type": metadata_text(payload, COMPLETION_RESULT_FOLLOW_UP_PROMPT_TYPE_FIELD),
        "detail": metadata_text(payload, COMPLETION_RESULT_ACTIVE_TASK_DETAIL_FIELD),
        "previous_response": "continue",
    }


def extract_direct_verify_request(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = dict(metadata or {}) if isinstance(metadata, dict) else {}
    if not metadata_requests_direct_verification(payload):
        return None
    action = metadata_text(payload, COMPLETION_RESULT_VERIFICATION_ACTION_FIELD)
    if not action:
        return None
    path = metadata_text(payload, COMPLETION_RESULT_VERIFICATION_PATH_FIELD, ".") or "."
    pytest_args = tuple(
        str(item or "").strip()
        for item in (payload.get(COMPLETION_RESULT_VERIFICATION_PYTEST_ARGS_FIELD) or payload.get("verificationPytestArgs") or ())
        if str(item or "").strip()
    )
    return {
        "action": action,
        "path": path,
        "pytest_args": pytest_args,
    }
