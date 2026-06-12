"""Task-contract policy helpers used by completion gating."""

from __future__ import annotations

from typing import Any

from ..task.contract import (
    PLANNER_BLOCKED_STATUS,
    PLANNER_INVALID_STATUS,
)
from ..task.intent import (
    accepts_final_response_task_type,
    is_plain_answer_task_type,
    is_read_only_blocking_requirement_kind,
    is_read_only_blocking_tool_name,
    is_read_only_task_type,
)

_BLOCKING_PLANNER_STATUSES = frozenset({PLANNER_BLOCKED_STATUS, PLANNER_INVALID_STATUS})


def contract_allows_plain_answer(task_contract: Any) -> bool:
    return bool(
        task_contract is not None
        and is_plain_answer_task_type(getattr(task_contract, "task_type", None))
        and getattr(task_contract, "allow_no_tool_final", False)
        and not tuple(getattr(task_contract, "requirements", ()) or ())
    )


def contract_is_read_only(task_contract: Any) -> bool:
    task_type = str(getattr(task_contract, "task_type", "") or "")
    if is_read_only_task_type(task_type):
        return True
    for requirement in getattr(task_contract, "requirements", ()) or ():
        if is_read_only_blocking_requirement_kind(str(getattr(requirement, "kind", "") or "")):
            return False
    for tool_name in getattr(task_contract, "required_tools", ()) or ():
        if is_read_only_blocking_tool_name(tool_name):
            return False
    return False


def is_blocking_planner_status(status: str | None) -> bool:
    return str(status or "").strip().lower() in _BLOCKING_PLANNER_STATUSES


def contract_has_completion_criteria(task_contract: Any) -> bool:
    return bool(getattr(task_contract, "requirements", ()) or getattr(task_contract, "acceptance_criteria", ()))


def contract_accepts_final_response(task_contract: Any) -> bool:
    if task_contract is None or contract_has_completion_criteria(task_contract):
        return False
    if not bool(getattr(task_contract, "final_answer_required", True)):
        return False
    if not bool(getattr(task_contract, "allow_no_tool_final", False)):
        return False
    task_type = str(getattr(task_contract, "task_type", "") or "").strip()
    return accepts_final_response_task_type(task_type)
