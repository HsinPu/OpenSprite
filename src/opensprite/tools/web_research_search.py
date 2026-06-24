"""Search result helpers for web research."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ..config.defaults import DEFAULT_WEB_SEARCH_PROVIDER
from ..config.schema import WebSearchToolConfig
from .web_research_candidates import dedupe_search_items, official_domain_hints
from .web_research_payloads import query_attempt_payload, search_attempt_payload
from .web_research_queries import dedupe_query_strings, official_site_queries, site_domain_hints
from .web_research_urls import canonicalize_url, clean_text, domain_from_url, is_fetchable_url
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


async def apply_official_site_search(
    *,
    query: str,
    research_queries: list[str],
    search_items: list[dict[str, Any]],
    search_provider: str,
    search_backend: str,
    search_attempts: list[dict[str, Any]],
    query_attempts: list[dict[str, Any]],
    count: int,
    freshness: str,
    search_queries: SearchQuery,
) -> tuple[
    list[str],
    list[dict[str, Any]],
    str,
    str,
    list[dict[str, Any]],
    list[dict[str, Any]],
    set[str],
]:
    official_domains = official_domain_hints(" ".join(research_queries), search_items) | site_domain_hints(
        research_queries
    )
    site_queries = official_site_queries(query, official_domains, existing_queries=research_queries)
    if not site_queries:
        return (
            research_queries,
            search_items,
            search_provider,
            search_backend,
            search_attempts,
            query_attempts,
            official_domains,
        )

    site_items, site_provider, site_backend, site_attempts, site_query_attempts = await search_queries(
        queries=site_queries,
        count=count,
        freshness=freshness,
    )
    search_attempts.extend(site_attempts)
    query_attempts.extend(site_query_attempts)
    research_queries = dedupe_query_strings([*research_queries, *site_queries])
    if site_items:
        search_items = dedupe_search_items(
            [*site_items, *search_items],
            limit=max(count * max(len(research_queries), 1), count),
        )
        official_domains.update(official_domain_hints(" ".join(research_queries), search_items))
        official_domains.update(site_domain_hints(research_queries))
        search_provider = site_provider or search_provider
        search_backend = site_backend or search_backend

    return (
        research_queries,
        search_items,
        search_provider,
        search_backend,
        search_attempts,
        query_attempts,
        official_domains,
    )


async def search_with_fallback(
    *,
    query: str,
    count: int,
    freshness: str,
    search_config: WebSearchToolConfig,
    search_tool: Any,
    custom_search_tool: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str, str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    last_provider = getattr(search_tool, "provider", search_config.provider)
    last_backend = ""
    if custom_search_tool:
        providers = [str(last_provider or search_config.provider or DEFAULT_WEB_SEARCH_PROVIDER)]
    else:
        providers = search_provider_order(
            search_config,
            configured_provider=str(last_provider or ""),
        )
    for provider in providers:
        tool = search_tool_for_provider(
            provider,
            search_config=search_config,
            search_tool=search_tool,
            custom_search_tool=custom_search_tool,
        )
        result = await tool._execute(query=query, count=count, freshness=freshness)
        payload = parse_json_object(result)
        provider_name = str((payload or {}).get("provider") or getattr(tool, "provider", provider) or provider)
        backend_name = str((payload or {}).get("backend") or "")
        last_provider = provider_name
        last_backend = backend_name
        items = dedupe_search_items(coerce_search_items(payload or {}), limit=count) if payload else []
        fetchable_count = sum(1 for item in items if is_fetchable_url(item.get("url")))
        attempts.append(
            search_attempt_payload(
                configured_provider=provider,
                provider=provider_name,
                backend=backend_name,
                payload=payload,
                items=items,
                raw_result=result,
                fetchable_count=fetchable_count,
            )
        )
        if payload is not None and fetchable_count > 0:
            return (
                payload,
                [
                    {
                        **item,
                        "search_provider": provider_name,
                        "search_backend": backend_name,
                        "search_freshness": str((payload or {}).get("freshness") or freshness),
                        "source_query": query,
                    }
                    for item in items
                ],
                provider_name,
                backend_name,
                attempts,
            )
    return None, [], str(last_provider or ""), str(last_backend or ""), attempts


def search_tool_for_provider(
    provider: str,
    *,
    search_config: WebSearchToolConfig,
    search_tool: Any,
    custom_search_tool: bool,
) -> Any:
    if custom_search_tool:
        return search_tool
    if provider == getattr(search_tool, "provider", ""):
        return search_tool
    return WebSearchTool(config=search_config.model_copy(update={"provider": provider}))


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
