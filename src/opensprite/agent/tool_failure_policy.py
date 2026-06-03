"""Shared policy for tool failures that should not block completion."""

from __future__ import annotations

from typing import Any

from ..tool_names import BATCH_TOOL_NAME
from .execution import ExecutionResult
from .history_retrieval_policy import is_history_retrieval_tool_name
from .task_artifact import TaskArtifact
from .tool_groups import WORKSPACE_DISCOVERY_TOOLS
from .web_source_policy import (
    is_fetched_web_source_artifact_tool,
    is_web_discovery_tool,
    is_web_fetch_source_record_tool,
    is_web_research_source_artifact_tool,
    is_web_source_artifact_kind,
)


OPTIONAL_WORKSPACE_BATCH_FAILURE_TOOL = BATCH_TOOL_NAME


def has_only_optional_web_discovery_failures(execution_result: ExecutionResult) -> bool:
    failed_evidence = tuple(item for item in execution_result.tool_evidence if not item.ok)
    if not failed_evidence:
        return False
    has_successful_fetch_sources = has_successful_fetched_web_source_artifact(execution_result)
    for item in failed_evidence:
        if is_optional_web_discovery_failure_tool(item.name):
            continue
        if is_optional_web_fetch_failure_tool(item.name) and has_successful_fetch_sources:
            continue
        if tool_failure_is_non_exposed_permission_block(item.metadata):
            continue
        return False
    return True


def has_only_optional_workspace_discovery_failures(execution_result: ExecutionResult) -> bool:
    failed_evidence = tuple(item for item in execution_result.tool_evidence if not item.ok)
    if not failed_evidence:
        return False
    if not any(item.ok and item.name in WORKSPACE_DISCOVERY_TOOLS for item in execution_result.tool_evidence):
        return False
    for item in failed_evidence:
        if item.name in WORKSPACE_DISCOVERY_TOOLS:
            continue
        if is_optional_workspace_batch_failure_tool(item.name) and execution_result.file_change_count <= 0:
            continue
        if tool_failure_is_non_exposed_permission_block(item.metadata):
            continue
        return False
    return True


def has_only_optional_history_retrieval_failures(execution_result: ExecutionResult) -> bool:
    failed_evidence = tuple(item for item in execution_result.tool_evidence if not item.ok)
    if not failed_evidence:
        return False
    if not any(item.ok and is_history_retrieval_tool_name(item.name) for item in execution_result.tool_evidence):
        return False
    for item in failed_evidence:
        if is_history_retrieval_tool_name(item.name):
            continue
        if tool_failure_is_non_exposed_permission_block(item.metadata):
            continue
        return False
    return True


def has_successful_fetched_web_source_artifact(execution_result: ExecutionResult) -> bool:
    for artifact in execution_result.task_artifacts:
        if not is_web_source_artifact_kind(artifact.kind) or not artifact.ok:
            continue
        sources = artifact.metadata.get("sources") if isinstance(artifact.metadata, dict) else None
        if is_fetched_web_source_artifact_tool(artifact.source_tool) and isinstance(sources, list) and sources:
            return True
        if (
            is_web_research_source_artifact_tool(artifact.source_tool)
            and web_research_artifact_has_successful_fetch(artifact)
        ):
            return True
    return False


def tool_failure_is_non_exposed_permission_block(metadata: Any) -> bool:
    permission = metadata.get("permission") if isinstance(metadata, dict) else None
    return bool(
        isinstance(permission, dict)
        and permission.get("blocked") is True
        and permission.get("exposed") is False
    )


def is_optional_web_discovery_failure_tool(tool_name: str | None) -> bool:
    return is_web_discovery_tool(tool_name)


def is_optional_web_fetch_failure_tool(tool_name: str | None) -> bool:
    return is_web_fetch_source_record_tool(tool_name)


def is_optional_workspace_batch_failure_tool(tool_name: str | None) -> bool:
    return str(tool_name or "").strip() == OPTIONAL_WORKSPACE_BATCH_FAILURE_TOOL


def is_history_retrieval_failure_tool(tool_name: str | None) -> bool:
    return is_history_retrieval_tool_name(tool_name)


def web_research_artifact_has_successful_fetch(artifact: TaskArtifact) -> bool:
    metadata = artifact.metadata if isinstance(artifact.metadata, dict) else {}
    coverage = metadata.get("coverage") if isinstance(metadata.get("coverage"), dict) else {}
    if int(coverage.get("fetched_count") or 0) > 0:
        return True
    sources = metadata.get("sources")
    if not isinstance(sources, list):
        return False
    for source in sources:
        if not isinstance(source, dict):
            continue
        if not is_web_fetch_source_record_tool(source.get("tool_name")):
            continue
        if source.get("blocked_or_challenge") or source.get("is_too_short"):
            continue
        if int(source.get("content_chars") or 0) > 0 or source.get("has_main_content"):
            return True
    return False
