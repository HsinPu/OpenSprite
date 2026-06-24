"""Search result helpers for web research."""

from __future__ import annotations

import json
from typing import Any

from ..config.defaults import DEFAULT_WEB_SEARCH_PROVIDER
from ..config.schema import WebSearchToolConfig
from .web_research_urls import canonicalize_url, clean_text, domain_from_url
from .web_search import WebSearchTool


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
