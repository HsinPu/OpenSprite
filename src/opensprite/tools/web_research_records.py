"""Source record helpers for web research payloads."""

from __future__ import annotations

from typing import Any

from .web_research_urls import candidate_url_key


def source_records_for_search_items(
    search_items: list[dict[str, Any]],
    *,
    fetched_by_candidate_url: dict[str, dict[str, Any]],
    search_provider: str,
    search_backend: str,
) -> list[dict[str, Any]]:
    source_records: list[dict[str, Any]] = []
    for item in search_items:
        item_search_provider = str(item.get("search_provider") or search_provider)
        item_search_backend = str(item.get("search_backend") or search_backend)
        source_records.append(
            {
                **item,
                "tool_name": "web_search",
                "fetched": False,
                "search_provider": item_search_provider,
                "search_backend": item_search_backend,
            }
        )
        fetched = fetched_by_candidate_url.get(candidate_url_key(item))
        if fetched is not None:
            source_records.append({**fetched, "tool_name": "web_fetch", "fetched": True})
    return source_records
