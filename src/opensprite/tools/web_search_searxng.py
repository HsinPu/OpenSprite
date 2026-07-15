"""SearXNG web search provider."""

from __future__ import annotations

from typing import Any

import httpx

from ..utils.url import join_url_path
from .web_search_freshness import freshness_params
from .web_search_payloads import format_error, format_results


def clean_text_values(values: Any) -> list[str]:
    out: list[str] = []
    if isinstance(values, str):
        candidates = values.replace("\n", ",").split(",")
    elif isinstance(values, (list, tuple, set)):
        candidates = values
    else:
        candidates = []
    for value in candidates:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def searxng_scope_params(engines: Any, categories: Any) -> dict[str, str]:
    params: dict[str, str] = {}
    engine_values = clean_text_values(engines)
    category_values = clean_text_values(categories)
    if engine_values:
        params["engines"] = ",".join(engine_values)
    if category_values:
        params["categories"] = ",".join(category_values)
    return params


async def search_searxng(
    query: str,
    n: int,
    freshness: str,
    *,
    base_url: str,
    max_pages: int,
    engines: Any,
    categories: Any,
    searxng_proxy: str | None,
    client_factory: Any = httpx.AsyncClient,
) -> str:
    try:
        seen_results: set[str] = set()
        items: list[dict[str, str]] = []
        scope_params = searxng_scope_params(engines, categories)
        async with client_factory(proxy=searxng_proxy) as client:
            for page in range(1, max_pages + 1):
                response = await client.get(
                    join_url_path(base_url, "/search"),
                    params={
                        "q": query,
                        "format": "json",
                        "pageno": page,
                        **scope_params,
                        **freshness_params("searxng", freshness),
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                page_results = response.json().get("results", [])
                if not page_results:
                    break
                for item in page_results:
                    if not isinstance(item, dict):
                        continue
                    normalized = {
                        "title": str(item.get("title") or "").strip(),
                        "url": str(item.get("url") or "").strip(),
                        "content": str(item.get("content") or "").strip(),
                    }
                    if not normalized["title"] or not normalized["url"]:
                        continue
                    dedupe_key = normalized.get("url") or normalized.get("title")
                    if dedupe_key in seen_results:
                        continue
                    seen_results.add(dedupe_key)
                    items.append(normalized)
                    if len(items) >= n:
                        break
                if len(items) >= n:
                    break
        if not items:
            return format_error(
                query,
                "searxng",
                f"SearXNG returned no results for '{query}'.",
                backend="searxng",
                freshness=freshness,
            )
        return format_results(
            query,
            items,
            n,
            provider="searxng",
            backend="searxng",
            freshness=freshness,
        )
    except Exception as exc:
        return format_error(
            query,
            "searxng",
            str(exc),
            backend="searxng",
            freshness=freshness,
        )
