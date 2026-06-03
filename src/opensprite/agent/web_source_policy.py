"""Shared policy helpers for web source artifacts."""

from __future__ import annotations

from ..tool_names import WEB_FETCH_TOOL_NAME, WEB_RESEARCH_TOOL_NAME, WEB_SEARCH_TOOL_NAME

FETCHED_WEB_SOURCE_ARTIFACT_TOOLS = frozenset({WEB_FETCH_TOOL_NAME, "browser_navigate", "browser_snapshot"})
WEB_DISCOVERY_TOOLS = frozenset({WEB_SEARCH_TOOL_NAME, WEB_RESEARCH_TOOL_NAME})
WEB_SOURCE_ARTIFACT_TOOLS = frozenset(
    {
        WEB_SEARCH_TOOL_NAME,
        WEB_FETCH_TOOL_NAME,
        WEB_RESEARCH_TOOL_NAME,
        "browser_navigate",
        "browser_snapshot",
    }
)
WEB_SOURCE_EVIDENCE_TOOLS = frozenset({WEB_SEARCH_TOOL_NAME, WEB_FETCH_TOOL_NAME, WEB_RESEARCH_TOOL_NAME})
WEB_BROWSER_RESEARCH_TOOLS = frozenset({"browser_snapshot", "browser_scroll"})
WEB_HARNESS_RESEARCH_TOOLS = WEB_SOURCE_EVIDENCE_TOOLS | WEB_BROWSER_RESEARCH_TOOLS
WEB_FETCH_SOURCE_RECORD_TOOL = WEB_FETCH_TOOL_NAME
WEB_RESEARCH_SOURCE_ARTIFACT_TOOL = WEB_RESEARCH_TOOL_NAME
WEB_RESEARCH_TASK_TYPE = "web_research"
WEB_RESEARCH_TOOL_GROUP = "web_research"
WEB_SOURCE_ARTIFACT_KIND = "web_source"
SOURCE_ARTIFACT_CRITERION_KIND = "source_artifact"
SOURCE_DETAIL_CRITERION_KIND = "source_detail"
SOURCE_REFERENCE_CRITERION_KIND = "source_reference"
SOURCE_ACCEPTANCE_CRITERION_KINDS = frozenset(
    {
        SOURCE_ARTIFACT_CRITERION_KIND,
        SOURCE_DETAIL_CRITERION_KIND,
        SOURCE_REFERENCE_CRITERION_KIND,
    }
)
WEB_SOURCE_REQUIRED_EVIDENCE = (WEB_SOURCE_ARTIFACT_KIND, SOURCE_REFERENCE_CRITERION_KIND)


def is_web_source_artifact_kind(kind: str | None) -> bool:
    return str(kind or "").strip() == WEB_SOURCE_ARTIFACT_KIND


def is_fetched_web_source_artifact_tool(source_tool: str | None) -> bool:
    return str(source_tool or "").strip() in FETCHED_WEB_SOURCE_ARTIFACT_TOOLS


def is_web_source_evidence_tool(tool_name: str | None) -> bool:
    return str(tool_name or "").strip() in WEB_SOURCE_EVIDENCE_TOOLS


def is_web_discovery_tool(tool_name: str | None) -> bool:
    return str(tool_name or "").strip() in WEB_DISCOVERY_TOOLS


def is_web_research_source_artifact_tool(source_tool: str | None) -> bool:
    return str(source_tool or "").strip() == WEB_RESEARCH_SOURCE_ARTIFACT_TOOL


def is_web_research_task_type(task_type: str | None) -> bool:
    return str(task_type or "").strip() == WEB_RESEARCH_TASK_TYPE


def is_web_research_tool_group(tool_group: str | None) -> bool:
    return str(tool_group or "").strip() == WEB_RESEARCH_TOOL_GROUP


def is_source_acceptance_criterion_kind(kind: str | None) -> bool:
    return str(kind or "").strip() in SOURCE_ACCEPTANCE_CRITERION_KINDS


def is_web_fetch_source_record_tool(tool_name: str | None) -> bool:
    return str(tool_name or "").strip() == WEB_FETCH_SOURCE_RECORD_TOOL


def web_source_has_substantive_detail(source: dict[str, object]) -> bool:
    tool_name = str(source.get("tool_name") or "").strip()
    if not is_fetched_web_source_artifact_tool(tool_name):
        return False
    if is_web_fetch_source_record_tool(tool_name):
        if _truthy(source.get("blocked_or_challenge")):
            return False
        if "has_main_content" in source and not _truthy(source.get("has_main_content")):
            return False
        if _truthy(source.get("is_too_short")):
            return False
        content_chars = _coerce_int(source.get("content_chars"), default=0)
        min_content_chars = _coerce_int(source.get("min_content_chars"), default=0)
        if min_content_chars > 0 and content_chars < min_content_chars:
            return False
    return True


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                return int(float(stripped))
            except ValueError:
                return default
    return default
