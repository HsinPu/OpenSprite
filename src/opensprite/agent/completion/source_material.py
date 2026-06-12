"""Source-material helpers for completion quality and auto-continuation."""

from __future__ import annotations

from typing import Any

from ..execution import ExecutionResult
from ..task.contract import (
    TaskContract,
    contract_requests_source_material,
    is_source_artifact_criterion,
    is_source_detail_criterion,
)
from ...tools.evidence import (
    is_web_research_task_type,
    is_web_research_source_artifact_tool,
    is_web_source_evidence_tool,
    is_web_source_artifact_kind,
    web_source_has_substantive_detail,
)
from .value_utils import (
    QUALITY_TRUE_VALUES as _QUALITY_TRUE_VALUES,
    coerce_bool as _coerce_bool,
    coerce_int as _coerce_int,
    truncate as _truncate,
)


def execution_web_sources(execution_result: ExecutionResult) -> list[dict[str, object]]:
    sources: list[dict[str, object]] = []
    for artifact in execution_result.task_artifacts:
        if artifact.ok and is_web_source_artifact_kind(artifact.kind):
            sources.extend(_artifact_web_sources(artifact.metadata, source_tool=artifact.source_tool))
    return sources


def source_material_satisfies_contract(contract: TaskContract, execution_result: ExecutionResult) -> bool:
    """Return whether gathered web source material satisfies source acceptance criteria."""
    for criterion in contract.acceptance_criteria:
        if is_source_artifact_criterion(criterion):
            min_count = max(1, int(getattr(criterion, "min_count", 1) or 1))
            if len(execution_web_sources(execution_result)) < min_count:
                return False
        elif is_source_detail_criterion(criterion):
            min_count = max(1, int(getattr(criterion, "min_count", 1) or 1))
            if substantive_source_detail_count(execution_result) < min_count:
                return False
            if web_research_coverage_gap_detail(execution_result) is not None:
                return False
    return True


def source_material_gap_detail(execution_result: ExecutionResult) -> str | None:
    """Return structured web research coverage gap detail, when available."""
    return web_research_coverage_gap_detail(execution_result)


def task_contract_requires_web_source_evidence(task_contract: Any) -> bool:
    if is_web_research_task_type(getattr(task_contract, "task_type", None)):
        return True
    if contract_requests_source_material(task_contract):
        return True
    return any(
        is_web_source_evidence_tool(tool_name)
        for tool_name in getattr(task_contract, "required_tools", ()) or ()
    )


def source_artifact_traceability_gap_detail(contract: TaskContract, execution_result: ExecutionResult) -> str | None:
    """Return detail when source artifacts exist but lack traceable source metadata."""
    for criterion in contract.acceptance_criteria:
        if not is_source_artifact_criterion(criterion):
            continue
        min_count = max(1, int(getattr(criterion, "min_count", 1) or 1))
        artifact_count = sum(
            1
            for artifact in execution_result.task_artifacts
            if artifact.ok and is_web_source_artifact_kind(artifact.kind)
        )
        traceable_count = len(execution_web_sources(execution_result))
        if artifact_count > 0 and traceable_count < min_count:
            return (
                "- Missing traceable source metadata: url plus title/snippet "
                f"(need {min_count}, found {traceable_count})"
            )
    return None


def web_research_coverage_gap_detail(execution_result: ExecutionResult) -> str | None:
    for artifact in execution_result.task_artifacts:
        if not artifact.ok or not is_web_research_source_artifact_tool(artifact.source_tool):
            continue
        coverage = artifact.metadata.get("coverage") if isinstance(artifact.metadata, dict) else None
        if not isinstance(coverage, dict):
            continue
        missing_queries = _quality_string_list(coverage.get("queries_without_successful_fetch"))
        target_met = _truthy(coverage.get("target_met"))
        if target_met:
            continue

        target_fetch_count = _coerce_int(coverage.get("target_fetch_count"), default=0)
        fetched_count = _coerce_int(coverage.get("fetched_count"), default=0)
        if target_fetch_count > 0 and substantive_source_detail_count(execution_result) >= target_fetch_count:
            continue
        too_short_count = _coerce_int(coverage.get("too_short_count"), default=0)
        blocked_count = _coerce_int(coverage.get("blocked_count"), default=0)
        fetched_domains = _quality_string_list(coverage.get("fetched_domains"))
        details = ["- Web research coverage gap: fetched source coverage did not satisfy the research pass."]
        if not target_met:
            details.append(f"- Target fetch count not met: need {target_fetch_count}, fetched {fetched_count}.")
        if missing_queries:
            details.append(
                "- Queries with search results but no successful fetch: "
                f"{', '.join(missing_queries[:5])}."
            )
        failure_details = []
        if too_short_count > 0:
            failure_details.append(f"{too_short_count} too short")
        if blocked_count > 0:
            failure_details.append(f"{blocked_count} blocked or challenged")
        if failure_details:
            details.append(f"- Failed source details: {', '.join(failure_details)}.")
        if fetched_domains:
            details.append(f"- Fetched domains so far: {', '.join(fetched_domains[:5])}.")
        details.append(
            "- Retry `web_research` with focused `queries` for the missing angles, "
            "or fetch alternate URLs/domains before finalizing."
        )
        return "\n".join(details)
    return None


def substantive_source_detail_count(execution_result: ExecutionResult) -> int:
    seen: set[str] = set()
    count = 0
    for source in execution_web_sources(execution_result):
        if not web_source_has_substantive_detail(source):
            continue
        url = str(source.get("url") or "").strip().lower()
        key = url or f"{source.get('title') or ''}|{source.get('snippet') or ''}"
        if key in seen:
            continue
        seen.add(key)
        count += 1
    return count


def format_web_source_context(sources: list[dict[str, object]]) -> str:
    lines: list[str] = []
    seen_urls: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = str(source.get("title") or "").strip()
        snippet = _source_context_detail(source)
        label = title or url
        line = f"- {label}: {url}"
        if snippet:
            line += f" - {snippet}"
        lines.append(line)
        if len(lines) >= 6:
            return "\n".join(lines)
    return "\n".join(lines)


def _artifact_web_sources(metadata: dict[str, object], *, source_tool: str = "") -> list[dict[str, object]]:
    raw_sources = metadata.get("sources") if isinstance(metadata, dict) else None
    if not isinstance(raw_sources, list):
        return []
    sources: list[dict[str, object]] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            continue
        url = str(raw_source.get("url") or "").strip()
        title = str(raw_source.get("title") or "").strip()
        snippet = str(raw_source.get("snippet") or "").strip()
        if url and (title or snippet):
            source: dict[str, object] = {
                "url": url,
                "title": title,
                "snippet": snippet,
                "tool_name": str(raw_source.get("tool_name") or source_tool or "").strip(),
            }
            for key in (
                "content_chars",
                "is_too_short",
                "min_content_chars",
                "truncated",
                "extractor",
                "has_main_content",
                "blocked_or_challenge",
                "quality_score",
            ):
                if key in raw_source:
                    source[key] = raw_source[key]
            sources.append(source)
    return sources


def _source_context_detail(source: dict[str, object]) -> str:
    raw_detail = str(source.get("content") or source.get("snippet") or "").strip()
    detail = " ".join(raw_detail.split())
    if not detail:
        return ""
    tool_name = str(source.get("tool_name") or "").strip().lower()
    prefix = ""
    max_chars = 260
    if tool_name == "web_fetch":
        prefix = "fetched content"
        char_count = _coerce_int(source.get("content_chars"), default=0)
        if char_count > 0:
            prefix += f" ({char_count} chars)"
        prefix += ": "
        max_chars = 900
    return f"{prefix}{_truncate(detail, max_chars=max_chars)}"


def _truthy(value: object) -> bool:
    return _coerce_bool(value, truthy_values=_QUALITY_TRUE_VALUES)


def _quality_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        key = text.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out
