"""Payload helpers for web research."""

from __future__ import annotations

import json
from typing import Any

from .web_research_urls import candidate_domain, candidate_query_label, clean_text


def research_payload(
    *,
    query: str,
    freshness: str,
    search_provider: str,
    search_backend: str,
    search_items: list[dict[str, Any]],
    fetched_sources: list[dict[str, Any]],
    failed_sources: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
    queries: list[str] | None = None,
    target_fetch_count: int | None = None,
    search_attempts: list[dict[str, Any]] | None = None,
    query_attempts: list[dict[str, Any]] | None = None,
) -> str:
    research_queries = queries or [query]
    coverage = research_coverage(
        queries=research_queries,
        target_fetch_count=target_fetch_count or len(fetched_sources),
        search_items=search_items,
        fetched_sources=fetched_sources,
        failed_sources=failed_sources,
    )
    return json.dumps(
        {
            "type": "web_research",
            "query": query,
            "queries": research_queries,
            "url": "",
            "final_url": "",
            "title": "",
            "content": "\n\n".join(str(item.get("content") or "") for item in fetched_sources if item.get("content")),
            "summary": f"Web research for: {query}",
            "provider": search_provider,
            "backend": search_backend,
            "extractor": "web_research",
            "status": None,
            "truncated": any(bool(item.get("truncated")) for item in fetched_sources),
            "content_type": "application/json",
            "freshness": freshness,
            "items": search_items,
            "fetched_sources": fetched_sources,
            "failed_sources": failed_sources,
            "sources": sources if sources is not None else fetched_sources,
            "source_count": len(sources if sources is not None else fetched_sources),
            "fetched_count": len(fetched_sources),
            "search_attempts": search_attempts or [],
            "query_attempts": query_attempts or [],
            "coverage": coverage,
        },
        ensure_ascii=False,
    )


def query_attempt_payload(
    query: str,
    provider: str,
    backend: str,
    payload: dict[str, Any] | None,
    items: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "query": query,
        "provider": provider,
        "backend": backend,
        "ok": payload is not None and bool(items),
        "result_count": len(items),
        "search_attempts": attempts,
    }


def search_attempt_payload(
    *,
    configured_provider: str,
    provider: str,
    backend: str,
    payload: dict[str, Any] | None,
    items: list[dict[str, Any]],
    raw_result: str,
    fetchable_count: int,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "configured_provider": configured_provider,
        "backend": backend,
        "ok": payload is not None and fetchable_count > 0,
        "result_count": len(items),
        "fetchable_count": fetchable_count,
        "error": str((payload or {}).get("error") or ("" if payload is not None else raw_result or ""))[:500],
    }


def research_coverage(
    *,
    queries: list[str],
    target_fetch_count: int,
    search_items: list[dict[str, Any]],
    fetched_sources: list[dict[str, Any]],
    failed_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    fetched_queries = ordered_clean_values(candidate_query_label(source) for source in fetched_sources)
    fetched_domains = ordered_clean_values(candidate_domain(source) for source in fetched_sources)
    queries_with_search_results = ordered_clean_values(candidate_query_label(item) for item in search_items)
    fetched_query_keys = {query.lower() for query in fetched_queries}
    queries_without_successful_fetch = [
        query
        for query in queries_with_search_results
        if query.lower() not in fetched_query_keys
    ]
    too_short_count = sum(
        1
        for source in failed_sources
        if bool(source.get("is_too_short")) or str(source.get("reason") or "") == "fetched content was too short"
    )
    blocked_count = sum(
        1
        for source in failed_sources
        if bool(source.get("blocked_or_challenge"))
        or str(source.get("reason") or "") == "fetched content looked blocked or challenged"
    )
    missing_url_count = sum(1 for source in failed_sources if str(source.get("reason") or "") == "missing url")
    return {
        "target_fetch_count": max(int(target_fetch_count or 0), 0),
        "target_met": len(fetched_sources) >= max(int(target_fetch_count or 0), 0),
        "search_result_count": len(search_items),
        "fetched_count": len(fetched_sources),
        "failed_count": len(failed_sources),
        "too_short_count": too_short_count,
        "blocked_count": blocked_count,
        "missing_url_count": missing_url_count,
        "fetched_domains": fetched_domains,
        "fetched_domain_count": len(fetched_domains),
        "fetched_queries": fetched_queries,
        "fetched_query_count": len(fetched_queries),
        "queries_with_search_results": queries_with_search_results,
        "queries_without_successful_fetch": queries_without_successful_fetch,
    }


def ordered_clean_values(values: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = clean_text(value)
        key = text.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out
