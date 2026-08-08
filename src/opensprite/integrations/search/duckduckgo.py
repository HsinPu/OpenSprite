"""DuckDuckGo web search provider."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from ...modules.search.web_policy import (
    DUCKDUCKGO_FRESHNESS as _DUCKDUCKGO_FRESHNESS,
    normalize_freshness as _normalize_freshness,
)
from ...modules.search.presentation import (
    format_error as _format_error,
    format_results as _format_results,
)


async def search_duckduckgo(query: str, n: int, freshness: str) -> str:
    """Search DuckDuckGo through the ddgs package."""
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError:
        return _format_error(
            query,
            "duckduckgo",
            "ddgs package is not installed. Install OpenSprite dependencies and retry.",
            backend="ddgs",
            freshness=freshness,
        )

    safe_limit = max(1, int(n))
    timelimit: str | None = _DUCKDUCKGO_FRESHNESS.get(
        _normalize_freshness(freshness, default="none")
    )

    def _run_ddgs_search() -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        search_kwargs: dict[str, Any] = {"max_results": safe_limit}
        if timelimit:
            search_kwargs["timelimit"] = timelimit
        with DDGS() as client:
            for i, hit in enumerate(client.text(query, **search_kwargs)):
                if i >= safe_limit:
                    break
                url = str(hit.get("href") or hit.get("url") or "")
                title = str(hit.get("title") or "")
                if not title or not url:
                    continue
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "content": str(hit.get("body") or hit.get("content") or ""),
                    }
                )
        return results

    try:
        items = await asyncio.to_thread(_run_ddgs_search)
    except Exception as exc:
        logger.warning("DDGS search failed: %s", exc)
        return _format_error(
            query,
            "duckduckgo",
            f"DDGS search failed: {exc}",
            backend="ddgs",
            freshness=freshness,
        )

    if not items:
        logger.warning("DDGS returned no results for query: %s", query)
        return _format_error(
            query,
            "duckduckgo",
            f"DDGS returned no results for '{query}'.",
            backend="ddgs",
            freshness=freshness,
        )
    return _format_results(
        query,
        items,
        n,
        provider="duckduckgo",
        backend="ddgs",
        freshness=freshness,
    )
