"""Jina web search provider."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import httpx

from .web_search_freshness import freshness_params
from .web_search_payloads import format_error, format_results

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


async def search_jina(
    query: str,
    n: int,
    freshness: str,
    *,
    api_key: str,
    proxy: str | None,
    client_factory: Any = httpx.AsyncClient,
) -> str:
    try:
        headers = {"User-Agent": USER_AGENT}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        params = freshness_params("jina", freshness)
        query_string = f"q={quote_plus(query)}&format=json"
        if params:
            query_string += "&" + "&".join(
                f"{key}={quote_plus(value)}" for key, value in params.items()
            )
        async with client_factory(proxy=proxy) as client:
            response = await client.get(
                f"https://s.jina.ai/http://duckduckgo.com/?{query_string}",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
        return format_results(
            query,
            [
                {
                    "title": f"Jina summary for {query}",
                    "url": "",
                    "content": response.text,
                }
            ],
            n,
            provider="jina",
            freshness=freshness,
        )
    except Exception as exc:
        return format_error(query, "jina", str(exc), freshness=freshness)
