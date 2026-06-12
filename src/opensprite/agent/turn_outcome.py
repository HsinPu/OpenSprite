"""Turn outcome metadata and final response policies."""

from __future__ import annotations

from typing import Any

from ..storage import StoredWorkState
from .completion.verifier import COMPLETION_VERIFIER_NEXT_ACTION_ASK_USER
from .completion_gate import (
    CompletionBlockerMessages,
    CompletionGateResult,
    allows_nonfinal_response_replacement,
    completion_blocker_response,
    is_blocking_completion_status,
    is_complete_completion_status,
)
from .execution import ExecutionResult
from .task.capabilities import PURE_ANSWER_TASK_TYPE
from .task.intent import PLANNING_ERROR_TASK_TYPE
from .task.progress import WorkProgressUpdate, metadata_is_work_progress_source
from .task.scorecard import task_contract_type
from .turn_input import metadata_text


TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD = "auto_continue_attempts"
TURN_METADATA_COMPLETION_GATE_FIELD = "completion_gate"
TURN_METADATA_COMPLETION_STATUS_FIELD = "completion_status"
TURN_METADATA_COMPLETION_REASON_FIELD = "completion_reason"
TURN_METADATA_WORK_PROGRESS_FIELD = "work_progress"
TURN_METADATA_TASK_CONTRACT_FIELD = "task_contract"
TURN_METADATA_TOOL_EVIDENCE_FIELD = "tool_evidence"
TURN_METADATA_TASK_ARTIFACTS_FIELD = "task_artifacts"
TURN_METADATA_DELEGATED_TASKS_FIELD = "delegated_tasks"
TURN_METADATA_ACTIVE_DELEGATE_TASK_ID_FIELD = "active_delegate_task_id"
TURN_METADATA_ACTIVE_DELEGATE_PROMPT_TYPE_FIELD = "active_delegate_prompt_type"
MEDIA_ONLY_TURN_REASON = "media_only"
LLM_NOT_CONFIGURED_TURN_REASON = "llm_not_configured"
TASK_CLARIFICATION_TURN_REASON = "task_clarification_requested"
LLM_NOT_CONFIGURED_LOG_REASON = "llm-not-configured"


def workflow_run_id(outcome: dict[str, Any]) -> str:
    return metadata_text(outcome, "workflow_run_id")


def task_checkpoint_metadata(
    *,
    aggregate_result: ExecutionResult,
    completion_result: CompletionGateResult,
    work_progress: WorkProgressUpdate,
    pass_index: int,
    auto_continue_attempts: int,
) -> dict[str, Any]:
    task_contract = getattr(aggregate_result, "task_contract", None)
    return {
        "schema_version": 1,
        "pass_index": max(1, pass_index),
        TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD: max(0, auto_continue_attempts),
        "task_type": task_contract_type(task_contract),
        "tool_selection": dict(aggregate_result.tool_selection or {}),
        TURN_METADATA_TASK_CONTRACT_FIELD: task_contract.to_metadata() if task_contract is not None else None,
        "completion": completion_result.to_metadata(),
        TURN_METADATA_WORK_PROGRESS_FIELD: work_progress.to_metadata(),
        "next_action": work_progress.next_action,
        "tool_evidence_count": len(aggregate_result.tool_evidence),
        "task_artifact_count": len(aggregate_result.task_artifacts),
    }


def final_response_after_exhausted_continuation(
    *,
    response: str,
    completion_result: CompletionGateResult,
    auto_continue_attempts: int,
    completion_blocker_messages: CompletionBlockerMessages,
) -> str:
    if not _should_replace_nonfinal_response(
        response=response,
        completion_result=completion_result,
        auto_continue_attempts=auto_continue_attempts,
    ):
        return response
    return completion_blocker_response(completion_result, completion_blocker_messages)


def _should_replace_nonfinal_response(
    *,
    response: str,
    completion_result: CompletionGateResult,
    auto_continue_attempts: int,
) -> bool:
    if is_complete_completion_status(completion_result.status):
        return False
    if completion_result.next_action == COMPLETION_VERIFIER_NEXT_ACTION_ASK_USER:
        return True
    if not (response or "").strip():
        return True
    if is_blocking_completion_status(completion_result.status):
        return False
    return allows_nonfinal_response_replacement(completion_result.status)


def is_tool_backed_task_contract(task_contract: Any) -> bool:
    task_type = str(getattr(task_contract, "task_type", "") or "").strip()
    if task_type in {"", PURE_ANSWER_TASK_TYPE, PLANNING_ERROR_TASK_TYPE}:
        return False
    return True


def can_replace_initial_work_state(state: StoredWorkState | None) -> bool:
    if state is None:
        return True
    metadata = state.metadata if isinstance(state.metadata, dict) else {}
    return (
        metadata_is_work_progress_source(metadata)
        and not state.completed_steps
        and not state.blockers
        and int(state.file_change_count or 0) == 0
        and not state.touched_paths
        and not state.delegated_tasks
    )
