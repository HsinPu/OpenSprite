"""Fetch helpers for web research."""

from __future__ import annotations

from typing import Any

from .web_research_search import parse_json_object
from .web_research_sources import merge_fetch_source
from .web_research_urls import candidate_url_key, clean_text


async def fetch_single_candidate(
    fetch_tool: Any,
    item: dict[str, Any],
    *,
    max_chars: int,
    query: str,
    search_provider: str,
    search_backend: str,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    canonical_url = candidate_url_key(item)
    url = clean_text(item.get("url"))
    item_search_provider = str(item.get("search_provider") or search_provider)
    item_search_backend = str(item.get("search_backend") or search_backend)
    try:
        fetch_result = await fetch_tool._execute(url=url, max_chars=max_chars)
    except Exception as exc:
        return canonical_url, None, {**item, "reason": f"web_fetch failed: {exc}"[:500]}
    fetch_payload = parse_json_object(fetch_result)
    if fetch_payload is None:
        return canonical_url, None, {
            **item,
            "reason": str(fetch_result or "web_fetch returned no structured result")[:500],
        }

    return canonical_url, merge_fetch_source(
        item,
        fetch_payload,
        query=str(item.get("source_query") or query),
        search_provider=item_search_provider,
        search_backend=item_search_backend,
    ), None
