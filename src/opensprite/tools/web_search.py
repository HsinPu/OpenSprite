"""Web search tool - multi-provider support."""

from __future__ import annotations

from typing import Any

import httpx

from ..config.schema import WebSearchToolConfig
from .base import Tool
from .web_search_freshness import web_search_request as _web_search_request
from .web_search_duckduckgo import search_duckduckgo
from .web_search_dispatch import (
    normalize_web_search_provider as _normalize_web_search_provider,
    web_search_provider as _web_search_provider,
)
from .web_search_payloads import format_error as _format_error
from .web_search_parameters import web_search_parameters as _web_search_parameters
from .web_search_searxng import (
    clean_text_values as _clean_text_values,
    search_searxng,
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
    description = (
        "Search the web for external sources. Freshness can search all time or use a fixed recent window. "
        "Returns structured JSON with titles, URLs, and snippets. Supports DuckDuckGo and SearXNG."
    )

    def __init__(self, config: WebSearchToolConfig | None = None):
        self.config = config or WebSearchToolConfig()
        self.searxng_proxy = _normalize_proxy(self.config.searxng_proxy)

    @property
    def parameters(self) -> dict[str, Any]:
        return _web_search_parameters(
            max_results=self.max_results,
            freshness=self.config.freshness,
        )

    @property
    def provider(self) -> str:
        return _normalize_web_search_provider(self.config.provider)

    @property
    def max_results(self) -> int:
        return self.config.max_results

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
        n, freshness = _web_search_request(
            count=count,
            max_results=self.max_results,
            freshness=kwargs.get("freshness"),
            default_freshness=self.config.freshness,
        )

        provider = self.provider

        searcher = self._provider_searcher(provider)
        if searcher is None:
            return _format_error(query, provider, f"unknown search provider '{provider}'")
        return await searcher(query, n, freshness)

    def _provider_searcher(self, provider: str):
        return _web_search_provider(
            provider,
            duckduckgo=self._search_duckduckgo,
            searxng=self._search_searxng,
        )

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
            searxng_proxy=self.searxng_proxy,
            client_factory=httpx.AsyncClient,
        )
