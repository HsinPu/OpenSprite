"""ExecutionResult aggregation helpers for multi-pass turns."""

from __future__ import annotations

from ..storage.base import selected_delegated_task
from .execution import ExecutionResult
from .task.contract import PLANNER_VALIDATED_STATUS, task_planner_status
from .task.intent import PLANNING_ERROR_TASK_TYPE
from .turn_outcome import is_tool_backed_task_contract


def aggregate_execution_results(results: list[ExecutionResult], *, content: str) -> ExecutionResult:
    """Aggregate multi-pass execution telemetry while keeping the final response."""
    delegated_tasks = tuple(task for result in results for task in result.delegated_tasks)
    selected_task = selected_delegated_task(delegated_tasks)
    latest_result = results[-1]
    return ExecutionResult(
        content=content,
        executed_tool_calls=sum(result.executed_tool_calls for result in results),
        file_change_count=sum(result.file_change_count for result in results),
        touched_paths=tuple(
            dict.fromkeys(
                path
                for result in results
                for path in result.touched_paths
            )
        ),
        delegated_tasks=delegated_tasks,
        workflow_outcomes=tuple(outcome for result in results for outcome in result.workflow_outcomes),
        active_delegate_task_id=next(
            (
                result.active_delegate_task_id
                for result in reversed(results)
                if result.active_delegate_task_id
            ),
            selected_task.task_id if selected_task is not None else None,
        ),
        active_delegate_prompt_type=next(
            (
                result.active_delegate_prompt_type
                for result in reversed(results)
                if result.active_delegate_prompt_type
            ),
            selected_task.prompt_type if selected_task is not None else None,
        ),
        used_configure_skill=any(result.used_configure_skill for result in results),
        had_tool_error=any(result.had_tool_error for result in results),
        verification_attempted=any(result.verification_attempted for result in results),
        verification_passed=any(result.verification_passed for result in results),
        stop_reason=latest_result.stop_reason,
        stop_metadata=dict(latest_result.stop_metadata or {}) if latest_result.stop_reason else {},
        compaction_handoff=next(
            (
                result.compaction_handoff
                for result in reversed(results)
                if result.compaction_handoff
            ),
            None,
        ),
        context_compactions=sum(result.context_compactions for result in results),
        context_compaction_events=[
            event
            for result in results
            for event in result.context_compaction_events
        ],
        llm_step_events=[
            event
            for result in results
            for event in result.llm_step_events
        ],
        reasoning_details=next(
            (
                result.reasoning_details
                for result in reversed(results)
                if result.reasoning_details
            ),
            None,
        ),
        assistant_internal_only_response=bool(latest_result.assistant_internal_only_response and not content.strip()),
        task_contract=select_aggregate_task_contract(results),
        tool_selection=next(
            (
                dict(result.tool_selection)
                for result in reversed(results)
                if result.tool_selection is not None
            ),
            None,
        ),
        tool_evidence=tuple(
            evidence
            for result in results
            for evidence in result.tool_evidence
        ),
        task_artifacts=tuple(
            artifact
            for result in results
            for artifact in result.task_artifacts
        ),
    )


def select_aggregate_task_contract(results: list[ExecutionResult]):
    """Keep the original tool-backed contract when a later retry only finalizes the answer."""
    latest_contract = next(
        (
            result.task_contract
            for result in reversed(results)
            if result.task_contract is not None
        ),
        None,
    )
    validated = next(
        (
            result.task_contract
            for result in reversed(results)
            if (
                result.task_contract is not None
                and task_planner_status(result.task_contract) == PLANNER_VALIDATED_STATUS
            )
        ),
        None,
    )
    if validated is not None and is_tool_backed_task_contract(validated):
        return validated
    tool_backed_validated = next(
        (
            result.task_contract
            for result in reversed(results)
            if (
                result.task_contract is not None
                and task_planner_status(result.task_contract) == PLANNER_VALIDATED_STATUS
                and is_tool_backed_task_contract(result.task_contract)
            )
        ),
        None,
    )
    if tool_backed_validated is not None:
        return tool_backed_validated
    if validated is not None:
        return validated
    return next(
        (
            result.task_contract
            for result in reversed(results)
            if result.task_contract is not None and result.task_contract.task_type != PLANNING_ERROR_TASK_TYPE
        ),
        latest_contract,
    )
