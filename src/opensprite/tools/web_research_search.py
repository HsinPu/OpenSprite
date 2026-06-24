"""Search result helpers for web research."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ..config.defaults import DEFAULT_WEB_SEARCH_PROVIDER
from ..config.schema import WebSearchToolConfig
from .web_research_candidates import dedupe_search_items
from .web_research_payloads import query_attempt_payload
from .web_research_urls import canonicalize_url, clean_text, domain_from_url
from .web_search import WebSearchTool

SearchQuery = Callable[
    ...,
    Awaitable[tuple[dict[str, Any] | None, list[dict[str, Any]], str, str, list[dict[str, Any]]]],
]


async def search_queries_with_fallback(
    *,
    queries: list[str],
    count: int,
    freshness: str,
    search_query: SearchQuery,
    search_concurrency: int,
) -> tuple[list[dict[str, Any]], str, str, list[dict[str, Any]], list[dict[str, Any]]]:
    all_items: list[dict[str, Any]] = []
    all_attempts: list[dict[str, Any]] = []
    query_attempts: list[dict[str, Any]] = []
    selected_provider = ""
    selected_backend = ""
    fallback_provider = ""
    fallback_backend = ""
    semaphore = asyncio.Semaphore(search_concurrency)

    async def run_query(current_query: str):
        async with semaphore:
            return await search_query(
                query=current_query,
                count=count,
                freshness=freshness,
            )

    results = await asyncio.gather(*(run_query(current_query) for current_query in queries))
    for current_query, result in zip(queries, results):
        payload, items, provider, backend, attempts = result
        all_attempts.extend(attempts)
        query_attempts.append(query_attempt_payload(current_query, provider, backend, payload, items, attempts))
        if not fallback_provider and provider:
            fallback_provider = provider
        if not fallback_backend and backend:
            fallback_backend = backend
        if items and not selected_provider and provider:
            selected_provider = provider
        if items and not selected_backend and backend:
            selected_backend = backend
        all_items.extend({**item, "source_query": current_query} for item in items)

    return (
        dedupe_search_items(all_items, limit=max(count * max(len(queries), 1), count)),
        selected_provider or fallback_provider,
        selected_backend or fallback_backend,
        all_attempts,
        query_attempts,
    )


def search_provider_order(config: WebSearchToolConfig, *, configured_provider: str) -> list[str]:
    configured = (configured_provider or config.provider or DEFAULT_WEB_SEARCH_PROVIDER).strip().lower() or DEFAULT_WEB_SEARCH_PROVIDER
    candidates = [configured]
    probe_tool = WebSearchTool(config=config)
    if str(config.searxng_url or "").strip():
        candidates.append("searxng")
    candidates.append("duckduckgo")
    if configured == "jina" or probe_tool.jina_api_key:
        candidates.append("jina")
    return dedupe_strings(candidates)


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = str(value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def parse_json_object(value: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(str(value or ""))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def coerce_search_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = payload.get("items", payload.get("results", []))
    if not isinstance(raw_items, list):
        return []
    out: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, 1):
        if not isinstance(raw_item, dict):
            continue
        url = clean_text(raw_item.get("url"))
        title = clean_text(raw_item.get("title"))
        snippet = clean_text(raw_item.get("content") or raw_item.get("snippet") or raw_item.get("summary"))
        canonical_url = canonicalize_url(url)
        out.append(
            {
                "rank": index,
                "title": title,
                "url": url,
                "canonical_url": canonical_url,
                "domain": domain_from_url(url),
                "content": snippet,
            }
        )
    return out
