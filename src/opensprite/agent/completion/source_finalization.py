"""Source finalization policy and ranking helpers."""

from __future__ import annotations

import re
from typing import Any

from ...tools.evidence import (
    is_source_acceptance_criterion_kind,
    is_web_fetch_source_record_tool,
    is_web_research_task_type,
    is_web_source_evidence_tool,
    is_web_source_artifact_kind,
)
from ..completion_gate import (
    BLOCKED_COMPLETION_STATUS,
    CompletionGateResult,
    is_incomplete_completion_status,
    needs_review_completion_status,
    normalize_completion_status,
)

OBJECTIVE_KEYWORD_RE = re.compile(r"[a-z0-9.:-]{3,}")
OBJECTIVE_CJK_SEQUENCE_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
OBJECTIVE_BRAND_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9-]{2,}\b")
OBJECTIVE_KEYWORD_STOP_WORDS = frozenset(
    {
        "please",
        "current",
        "latest",
        "\u5e6b\u6211",
        "\u76ee\u524d",
        "\u6700\u65b0",
        "\u8acb\u5217\u51fa",
        "\u4f86\u6e90\u7db2\u5740",
    }
)


def source_finalization_allowed(completion_result: CompletionGateResult, execution_result: Any) -> bool:
    if not (
        is_incomplete_completion_status(completion_result.status)
        or normalize_completion_status(completion_result.status) == BLOCKED_COMPLETION_STATUS
        or needs_review_completion_status(completion_result.status)
    ):
        return False
    return task_contract_requires_web_sources(getattr(execution_result, "task_contract", None))


def task_contract_requires_web_sources(contract: Any) -> bool:
    if contract is None:
        return False
    if is_web_research_task_type(getattr(contract, "task_type", None)):
        return True
    if any(is_web_source_evidence_tool(tool_name) for tool_name in getattr(contract, "required_tools", ()) or ()):
        return True
    for requirement in getattr(contract, "requirements", ()) or ():
        if any(is_web_source_evidence_tool(tool_name) for tool_name in getattr(requirement, "tools", ()) or ()):
            return True
    for criterion in getattr(contract, "acceptance_criteria", ()) or ():
        if is_source_acceptance_criterion_kind(getattr(criterion, "kind", None)):
            return True
    return False


def rank_web_sources_for_objective(sources: list[dict[str, Any]], objective: str) -> list[dict[str, Any]]:
    if not objective:
        return sources
    return sorted(
        sources,
        key=lambda source: web_source_relevance_score(source, objective),
        reverse=True,
    )


def web_source_relevance_score(source: dict[str, Any], objective: str) -> int:
    keywords = _objective_keywords(objective)
    if not keywords:
        return 0
    score = 0
    domain = _web_source_text(source, "domain").lower()
    if not domain:
        url = _web_source_text(source, "url").lower()
        domain = re.sub(r"^https?://", "", url).split("/", 1)[0]
    domain_label = _domain_brand_label(domain)
    if domain_label and domain_label in _objective_brand_tokens(objective):
        score += 10
    haystack = " ".join(
        _web_source_text(source, key)
        for key in ("title", "url", "snippet", "content", "domain")
    ).lower()
    score += sum(1 for keyword in keywords if keyword in haystack)
    return score


def web_source_body_text(source: dict[str, Any]) -> str:
    return _web_source_text(source, "snippet") or _web_source_text(source, "content")


def _web_source_text(source: dict[str, Any], key: str) -> str:
    return str(source.get(key) or "")


def _objective_keywords(objective: str) -> set[str]:
    text = str(objective or "").lower()
    keywords: set[str] = set()
    keywords.update(OBJECTIVE_KEYWORD_RE.findall(text))
    for cjk_text in OBJECTIVE_CJK_SEQUENCE_RE.findall(text):
        keywords.add(cjk_text)
        for size in (2, 3, 4):
            for index in range(0, max(len(cjk_text) - size + 1, 0)):
                keywords.add(cjk_text[index : index + size])
    return {keyword for keyword in keywords if keyword not in OBJECTIVE_KEYWORD_STOP_WORDS}


def _objective_brand_tokens(objective: str) -> set[str]:
    return {
        token.lower()
        for token in OBJECTIVE_BRAND_TOKEN_RE.findall(str(objective or ""))
    }


def _domain_brand_label(domain: str) -> str:
    labels = str(domain or "").lower().removeprefix("www.").split(".")
    labels = [label for label in labels if label]
    if len(labels) < 2:
        return ""
    return labels[-2].replace("-", "")


def source_finalization_available(
    completion_result: CompletionGateResult,
    execution_result: ExecutionResult | None,
) -> bool:
    return bool(source_finalization_sources(completion_result, execution_result))


def source_finalization_sources(
    completion_result: CompletionGateResult,
    execution_result: ExecutionResult | None,
) -> list[dict[str, Any]]:
    if execution_result is None:
        return []
    if not source_finalization_allowed(completion_result, execution_result):
        return []
    evidence_urls = _completion_evidence_urls(completion_result)
    objective = _execution_objective(execution_result)
    sources = _merge_web_sources(
        _substantive_web_sources(execution_result),
        _merge_web_sources(
            _web_sources_matching_evidence_urls(execution_result, evidence_urls),
            _web_sources_matching_base_url_context(execution_result, objective),
        ),
    )
    if not sources:
        return []
    sources = rank_web_sources_for_objective(sources, objective)
    if execution_result.had_tool_error:
        top_score = web_source_relevance_score(sources[0], objective) if sources else 0
        if top_score <= 0:
            return []
    return sources


def _substantive_web_sources(execution_result: ExecutionResult) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for artifact in execution_result.task_artifacts:
        if not artifact.ok or not is_web_source_artifact_kind(artifact.kind):
            continue
        raw_sources = artifact.metadata.get("sources") if isinstance(artifact.metadata, dict) else None
        if not isinstance(raw_sources, list):
            continue
        for raw_source in raw_sources:
            if not isinstance(raw_source, dict):
                continue
            url = _web_source_url(raw_source)
            if not url or url in seen_urls:
                continue
            content_chars = _coerce_positive_int(raw_source.get("content_chars"))
            is_too_short = bool(raw_source.get("is_too_short"))
            has_main_content = bool(raw_source.get("has_main_content"))
            if (
                is_web_fetch_source_record_tool(raw_source.get("tool_name"))
                and (content_chars >= 800 or has_main_content)
                and not is_too_short
            ):
                seen_urls.add(url)
                sources.append(raw_source)
    return sources


def _web_source_url(source: dict[str, Any]) -> str:
    return _web_source_text(source, "url")


def _completion_evidence_urls(completion_result: CompletionGateResult) -> tuple[str, ...]:
    text = " ".join(
        (
            str(completion_result.reason or ""),
            str(completion_result.active_task_detail or ""),
            " ".join(str(item or "") for item in completion_result.missing_evidence),
        )
    )
    return tuple(dict.fromkeys(_extract_urls(text)))


def _merge_web_sources(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for source in (*primary, *secondary):
        url = _web_source_url(source)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        merged.append(source)
    return merged


def _web_sources_matching_evidence_urls(
    execution_result: ExecutionResult,
    evidence_urls: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not evidence_urls:
        return []
    sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for artifact in execution_result.task_artifacts:
        if not artifact.ok or not is_web_source_artifact_kind(artifact.kind):
            continue
        raw_sources = artifact.metadata.get("sources") if isinstance(artifact.metadata, dict) else None
        if not isinstance(raw_sources, list):
            continue
        for raw_source in raw_sources:
            if not isinstance(raw_source, dict):
                continue
            url = _web_source_url(raw_source)
            if not url or url in seen_urls:
                continue
            haystack = web_source_body_text(raw_source)
            if any(evidence_url in haystack for evidence_url in evidence_urls):
                seen_urls.add(url)
                sources.append(raw_source)
    return sources


def _web_sources_matching_base_url_context(
    execution_result: ExecutionResult,
    objective: str,
) -> list[dict[str, Any]]:
    if not _objective_requests_base_url(objective):
        return []
    sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for artifact in execution_result.task_artifacts:
        if not artifact.ok or not is_web_source_artifact_kind(artifact.kind):
            continue
        raw_sources = artifact.metadata.get("sources") if isinstance(artifact.metadata, dict) else None
        if not isinstance(raw_sources, list):
            continue
        for raw_source in raw_sources:
            if not isinstance(raw_source, dict):
                continue
            url = _web_source_url(raw_source)
            if not url or url in seen_urls:
                continue
            if _source_base_url_candidates([raw_source]):
                seen_urls.add(url)
                sources.append(raw_source)
    return sources


def _objective_requests_base_url(objective: str) -> bool:
    text = str(objective or "").lower()
    return "base url" in text or "base_url" in text or "api base" in text


def _source_base_url_candidates(sources: list[dict[str, Any]]) -> list[str]:
    candidates: list[str] = []
    for source in sources:
        text = web_source_body_text(source)
        for match in re.finditer(r"https?://\S+", text):
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end].lower()
            if "base url" not in context and "base_url" not in context and "api base" not in context:
                continue
            candidates.append(_clean_extracted_url(match.group(0)))
    return candidates


def _extract_urls(text: str) -> list[str]:
    return [_clean_extracted_url(match.group(0)) for match in re.finditer(r"https?://\S+", str(text or ""))]


def _clean_extracted_url(url: str) -> str:
    return str(url or "").strip().rstrip(".,;:)]}>\"'")


def _execution_objective(execution_result: ExecutionResult) -> str:
    task_contract = getattr(execution_result, "task_contract", None)
    return str(getattr(task_contract, "objective", "") or "").strip()


def _coerce_positive_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0
