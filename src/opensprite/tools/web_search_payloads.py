"""Structured payload formatting for web search results."""

from __future__ import annotations

import json
import re
from typing import Any


def strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text


def normalize_text(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def format_results(
    query: str,
    items: list[dict[str, Any]],
    n: int,
    *,
    provider: str,
    backend: str,
    **metadata: Any,
) -> str:
    """Format a compact web-search result payload."""
    normalized_items: list[dict[str, str]] = []
    for item in items[:n]:
        normalized_items.append(
            {
                "title": normalize_text(strip_tags(str(item.get("title", "") or ""))),
                "url": str(item.get("url", "") or ""),
                "content": normalize_text(strip_tags(str(item.get("content", "") or ""))),
            }
        )
    payload = {
        "type": "web_search",
        "ok": True,
        "query": query,
        "summary": f"Search results for: {query}",
        "provider": provider,
        "backend": backend,
        "items": normalized_items,
    }
    payload.update({key: value for key, value in metadata.items() if value is not None})
    return json.dumps(payload, ensure_ascii=False)


def format_error(query: str, provider: str, error: str, **metadata: Any) -> str:
    """Format a compact web-search error payload."""
    payload = {
        "type": "web_search",
        "ok": False,
        "query": query,
        "summary": f"Search failed for: {query}",
        "provider": provider,
        "items": [],
        "error": str(error or "").strip(),
        "error_type": "WebSearchError",
        "category": "web_search_error",
    }
    payload.update({key: value for key, value in metadata.items() if value is not None})
    return json.dumps(payload, ensure_ascii=False)
