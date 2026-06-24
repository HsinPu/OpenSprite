"""Web search tool - multi-provider support."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote_plus

import httpx

from ..config.defaults import DEFAULT_WEB_SEARCH_PROVIDER
from ..config.schema import WebSearchToolConfig
from .base import Tool
from .validation import NON_EMPTY_STRING_PATTERN
from .web_search_freshness import (
    AUTO_FRESHNESS,
    FRESHNESS_VALUES,
    effective_freshness as _effective_freshness,
    freshness_params as _freshness_params,
    normalize_freshness as _normalize_freshness,
)
from .web_search_duckduckgo import search_duckduckgo
from .web_search_payloads import (
    format_error as _format_error,
    format_results as _format_results,
    normalize_text as _normalize,
    strip_tags as _strip_tags,
)
from .web_search_searxng import (
    clean_text_values as _clean_text_values,
    search_searxng,
    searxng_scope_params as _searxng_scope_params,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
def _normalize_proxy(proxy: Any) -> str | None:
    """Normalize optional proxy config for httpx."""
    if proxy is None:
        return None
    if isinstance(proxy, str):
        proxy = proxy.strip()
        return proxy or None
    return str(proxy)


class WebSearchTool(Tool):
    """Search the web using configured provider."""

    name = "web_search"
    description = "Search the web for external sources. The freshness setting controls recency: auto uses the configured default recent window, none searches all time, and fixed windows are respected. Returns structured JSON with titles, URLs, and snippets. Supports DuckDuckGo, SearXNG, Jina."

    def __init__(self, config: WebSearchToolConfig | None = None, proxy: str | None = None):
        self.config = config or WebSearchToolConfig()
        raw_proxy = proxy if proxy is not None else self.config.proxy
        self.proxy = _normalize_proxy(raw_proxy)

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query", "pattern": NON_EMPTY_STRING_PATTERN},
                "count": {
                    "type": "integer",
                    "description": f"Results (1-{self.max_results})",
                    "default": self.max_results,
                    "minimum": 1,
                    "maximum": self.max_results,
                },
                "freshness": {
                    "type": "string",
                    "enum": list(FRESHNESS_VALUES),
                    "description": "Recency filter. auto uses the configured default recent window; none searches all time; fixed windows are respected.",
                    "default": self.config.freshness,
                }
            },
            "required": ["query"]
        }

    @property
    def provider(self) -> str:
        return self.config.provider.strip().lower() or DEFAULT_WEB_SEARCH_PROVIDER

    @property
    def jina_api_key(self) -> str:
        return self.config.jina_api_key or os.environ.get("JINA_API_KEY", "")

    @property
    def max_results(self) -> int:
        return self.config.max_results

    @property
    def duckduckgo_max_pages(self) -> int:
        return self.config.duckduckgo_max_pages

    @property
    def searxng_max_pages(self) -> int:
        return self.config.searxng_max_pages

    @property
    def searxng_engines(self) -> list[str]:
        return _clean_text_values(self.config.searxng_engines)

    @property
    def searxng_categories(self) -> list[str]:
        return _clean_text_values(self.config.searxng_categories)

    async def _execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
        n = min(max(count or self.max_results, 1), self.max_results)
        freshness = _effective_freshness(kwargs.get("freshness"), self.config.freshness, query=query)

        provider = self.provider

        searcher = self._provider_searcher(provider)
        if searcher is None:
            return _format_error(query, provider, f"unknown search provider '{provider}'")
        return await searcher(query, n, freshness)

    def _provider_searcher(self, provider: str):
        searchers = {
            "duckduckgo": self._search_duckduckgo,
            "searxng": self._search_searxng,
            "jina": self._search_jina,
        }
        return searchers.get(provider)

    async def _search_duckduckgo(self, query: str, n: int, freshness: str) -> str:
        """Search DuckDuckGo through the ddgs package."""
        return await search_duckduckgo(query, n, freshness)

    async def _search_searxng(self, query: str, n: int, freshness: str) -> str:
        return await search_searxng(
            query,
            n,
            freshness,
            base_url=self.config.searxng_url,
            max_pages=self.searxng_max_pages,
            engines=self.searxng_engines,
            categories=self.searxng_categories,
            proxy=self.proxy,
            client_factory=httpx.AsyncClient,
        )

    async def _search_jina(self, query: str, n: int, freshness: str) -> str:
        try:
            headers = {"User-Agent": USER_AGENT}
            if self.jina_api_key:
                headers["Authorization"] = f"Bearer {self.jina_api_key}"
            params = _freshness_params("jina", freshness)
            query_string = f"q={quote_plus(query)}&format=json"
            if params:
                query_string += "&" + "&".join(f"{key}={quote_plus(value)}" for key, value in params.items())
            async with httpx.AsyncClient(proxy=self.proxy) as client:
                r = await client.get(
                    f"https://s.jina.ai/http://duckduckgo.com/?{query_string}",
                    headers=headers,
                    timeout=10.0
                )
                r.raise_for_status()
            return _format_results(
                query,
                [{
                    "title": f"Jina summary for {query}",
                    "url": "",
                    "content": r.text,
                }],
                n,
                provider="jina",
                freshness=freshness,
            )
        except Exception as e:
            return _format_error(query, "jina", str(e), freshness=freshness)
