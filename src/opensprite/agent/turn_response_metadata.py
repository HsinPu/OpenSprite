"""Response metadata builders for completed turns."""

from __future__ import annotations

from typing import Any

from .completion.results import CompletionGateResult
from .execution import ExecutionResult
from .task.progress import WorkProgressUpdate
from .turn_outcome import (
    TURN_METADATA_ACTIVE_DELEGATE_PROMPT_TYPE_FIELD,
    TURN_METADATA_ACTIVE_DELEGATE_TASK_ID_FIELD,
    TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD,
    TURN_METADATA_COMPLETION_GATE_FIELD,
    TURN_METADATA_COMPLETION_STATUS_FIELD,
    TURN_METADATA_DELEGATED_TASKS_FIELD,
    TURN_METADATA_TASK_ARTIFACTS_FIELD,
    TURN_METADATA_TASK_CONTRACT_FIELD,
    TURN_METADATA_TOOL_EVIDENCE_FIELD,
    TURN_METADATA_WORK_PROGRESS_FIELD,
)


def build_turn_response_metadata(
    *,
    response: str,
    aggregate_result: ExecutionResult,
    completion_result: CompletionGateResult,
    work_progress: WorkProgressUpdate,
    auto_continue_attempts: int,
    assistant_metadata: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    response_metadata = {
        "response_len": len(response or ""),
        "executed_tool_calls": aggregate_result.executed_tool_calls,
        "had_tool_error": aggregate_result.had_tool_error,
        "verification_attempted": aggregate_result.verification_attempted,
        "verification_passed": aggregate_result.verification_passed,
        "context_compactions": aggregate_result.context_compactions,
        TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD: auto_continue_attempts,
        TURN_METADATA_WORK_PROGRESS_FIELD: work_progress.to_metadata(),
    }
    status_metadata = {
        "executed_tool_calls": aggregate_result.executed_tool_calls,
        "had_tool_error": aggregate_result.had_tool_error,
        "verification_attempted": aggregate_result.verification_attempted,
        "verification_passed": aggregate_result.verification_passed,
        "context_compactions": aggregate_result.context_compactions,
        TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD: auto_continue_attempts,
        TURN_METADATA_COMPLETION_STATUS_FIELD: completion_result.status,
    }
    completion_metadata = completion_result.to_metadata()
    completion_metadata[TURN_METADATA_AUTO_CONTINUE_ATTEMPTS_FIELD] = auto_continue_attempts
    response_metadata[TURN_METADATA_COMPLETION_GATE_FIELD] = completion_metadata
    if aggregate_result.task_contract is not None:
        response_metadata[TURN_METADATA_TASK_CONTRACT_FIELD] = aggregate_result.task_contract.to_metadata()
    if aggregate_result.tool_evidence:
        response_metadata[TURN_METADATA_TOOL_EVIDENCE_FIELD] = [
            item.to_metadata() for item in aggregate_result.tool_evidence
        ]
    if aggregate_result.task_artifacts:
        response_metadata[TURN_METADATA_TASK_ARTIFACTS_FIELD] = [
            item.to_metadata() for item in aggregate_result.task_artifacts
        ]
    response_metadata[TURN_METADATA_DELEGATED_TASKS_FIELD] = [task.to_payload() for task in aggregate_result.delegated_tasks]
    response_metadata[TURN_METADATA_ACTIVE_DELEGATE_TASK_ID_FIELD] = aggregate_result.active_delegate_task_id
    response_metadata[TURN_METADATA_ACTIVE_DELEGATE_PROMPT_TYPE_FIELD] = aggregate_result.active_delegate_prompt_type
    if aggregate_result.stop_reason:
        response_metadata["stop_reason"] = aggregate_result.stop_reason
        status_metadata["stop_reason"] = aggregate_result.stop_reason
        if aggregate_result.stop_metadata:
            response_metadata["stop_metadata"] = dict(aggregate_result.stop_metadata)
            status_metadata["stop_metadata"] = dict(aggregate_result.stop_metadata)
    persisted_assistant_metadata = dict(assistant_metadata)
    if aggregate_result.reasoning_details:
        persisted_assistant_metadata["llm_reasoning_details"] = aggregate_result.reasoning_details
    return response_metadata, status_metadata, persisted_assistant_metadata
