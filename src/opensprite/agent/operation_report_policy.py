"""Shared policy for operations-task quality checks."""

from __future__ import annotations

from ..tool_names import EXECUTION_TOOL_NAMES
from .command_version_policy import command_inspects_git_repository_state
from .execution import ExecutionResult
from .harness_profile import OPERATIONS_TASK_TYPE


def is_operations_task_type(task_type: str | None) -> bool:
    return str(task_type or "").strip() == OPERATIONS_TASK_TYPE


def is_command_execution_tool_name(tool_name: str | None) -> bool:
    return str(tool_name or "").strip() in EXECUTION_TOOL_NAMES


def execution_has_failed_command_evidence(execution_result: ExecutionResult) -> bool:
    return any(
        is_command_execution_tool_name(evidence.name) and not evidence.ok
        for evidence in execution_result.tool_evidence
    )


def execution_confuses_command_version_with_repo_state(execution_result: ExecutionResult) -> bool:
    for evidence in execution_result.tool_evidence:
        command = ""
        if isinstance(evidence.metadata, dict):
            args = evidence.metadata.get("tool_args")
            if isinstance(args, dict):
                command = str(args.get("command") or "").lower()
        if command_inspects_git_repository_state(command):
            return True
    return False
