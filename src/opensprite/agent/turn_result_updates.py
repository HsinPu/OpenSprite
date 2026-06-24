"""ExecutionResult update helpers used while a turn runs."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..storage import StoredDelegatedTask
from ..storage.base import selected_delegated_task
from .execution import ExecutionResult
from .turn_outcome import workflow_run_id
from .workflow import is_workflow_failed_status


def with_delegated_tasks(
    result: ExecutionResult,
    delegated_tasks: tuple[StoredDelegatedTask, ...],
) -> ExecutionResult:
    selected_task = selected_delegated_task(delegated_tasks)
    return replace(
        result,
        delegated_tasks=delegated_tasks,
        active_delegate_task_id=selected_task.task_id if selected_task is not None else None,
        active_delegate_prompt_type=selected_task.prompt_type if selected_task is not None else None,
    )


def with_workflow_outcomes(
    result: ExecutionResult,
    workflow_outcomes: tuple[dict[str, Any], ...],
) -> ExecutionResult:
    return replace(result, workflow_outcomes=workflow_outcomes)


def merge_delegated_task_updates(
    existing: tuple[StoredDelegatedTask, ...],
    updates: tuple[StoredDelegatedTask, ...],
) -> tuple[StoredDelegatedTask, ...]:
    if not updates:
        return existing
    by_id = {task.task_id: task for task in existing if task.task_id}
    order = [task.task_id for task in existing if task.task_id]
    for update in updates:
        if not update.task_id:
            continue
        previous = by_id.pop(update.task_id, None)
        if update.task_id in order:
            order.remove(update.task_id)
        order.append(update.task_id)
        by_id[update.task_id] = StoredDelegatedTask(
            task_id=update.task_id,
            prompt_type=update.prompt_type or (previous.prompt_type if previous is not None else None),
            status=update.status or (previous.status if previous is not None else "unknown"),
            selected=bool(update.selected),
            summary=update.summary or (previous.summary if previous is not None else ""),
            error=(
                update.error
                if update.error
                else ""
                if update.status and not is_workflow_failed_status(update.status)
                else previous.error if previous is not None else ""
            ),
            child_session_id=update.child_session_id or (previous.child_session_id if previous is not None else None),
            last_child_run_id=update.last_child_run_id or (previous.last_child_run_id if previous is not None else None),
            metadata={**(previous.metadata if previous is not None else {}), **dict(update.metadata or {})},
            created_at=(
                previous.created_at
                if previous is not None and previous.created_at
                else update.created_at
            ),
            updated_at=update.updated_at or (previous.updated_at if previous is not None else 0.0),
        )
    tasks = tuple(by_id[task_id] for task_id in order if task_id in by_id)
    selected_task = selected_delegated_task(tuple(task for task in reversed(tasks)))
    if selected_task is None:
        return tasks
    return tuple(replace(task, selected=task.task_id == selected_task.task_id) for task in tasks)


def merge_workflow_outcomes(
    existing: tuple[dict[str, Any], ...],
    updates: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    by_id = {
        workflow_run_id(item): dict(item)
        for item in existing
        if isinstance(item, dict) and workflow_run_id(item)
    }
    order = [
        workflow_run_id(item)
        for item in existing
        if isinstance(item, dict) and workflow_run_id(item)
    ]
    for update in updates:
        if not isinstance(update, dict):
            continue
        workflow_run_id_value = workflow_run_id(update)
        if not workflow_run_id_value:
            continue
        if workflow_run_id_value in order:
            order.remove(workflow_run_id_value)
        order.append(workflow_run_id_value)
        by_id[workflow_run_id_value] = dict(update)
    return tuple(by_id[workflow_run_id_value] for workflow_run_id_value in order if workflow_run_id_value in by_id)
