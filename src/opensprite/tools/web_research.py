"""High-level web research orchestration tool."""

from __future__ import annotations

from typing import Any

from ..config.schema import WebFetchToolConfig, WebSearchToolConfig
from .base import Tool
from .web_fetch import WebFetchTool
from .web_research_candidates import (
    expand_llms_full_candidates as _expand_llms_full_candidates,
    prioritize_research_candidates as _prioritize_research_candidates,
)
from .web_research_payloads import research_payload as _research_payload
from .web_research_fetch import (
    fetch_research_candidates as _fetch_research_candidates_batch,
    fetch_single_candidate as _fetch_single_research_candidate,
)
from .web_research_queries import (
    normalize_research_params as _normalize_research_params,
    prepare_research_request as _prepare_research_request,
)
from .web_research_parameters import web_research_parameters as _web_research_parameters
from .web_research_records import source_records_for_search_items as _source_records_for_search_items
from .web_research_search import (
    apply_official_site_search as _apply_official_site_search,
    search_queries_with_fallback as _search_queries_with_fallback_batch,
    search_with_fallback as _search_with_fallback_helper,
)
from .web_search import WebSearchTool

_WEB_RESEARCH_FETCH_CONCURRENCY = 4
_WEB_RESEARCH_SEARCH_CONCURRENCY = 3


class WebResearchTool(Tool):
    """Search, dedupe, fetch, and return source material in one structured payload."""

    name = "web_research"
    description = (
        "Run a compact research pass for external information: search the web, dedupe/rank candidate URLs, "
        "fetch the most promising pages, skip too-short fetches when possible, and return traceable sources. "
        "Use this instead of separate web_search + web_fetch when the user asks for current web research."
    )

    def __init__(
        self,
        *,
        search_config: WebSearchToolConfig | None = None,
        fetch_config: WebFetchToolConfig | None = None,
        search_tool: WebSearchTool | None = None,
        fetch_tool: WebFetchTool | None = None,
    ):
        self.search_config = search_config or WebSearchToolConfig()
        self.fetch_config = fetch_config or WebFetchToolConfig()
        self._custom_search_tool = search_tool is not None
        self.search_tool = search_tool or WebSearchTool(config=self.search_config)
        self.fetch_tool = fetch_tool or WebFetchTool(
            max_chars=self.fetch_config.max_chars,
            max_response_size=self.fetch_config.max_response_size,
            timeout=self.fetch_config.timeout,
            prefer_trafilatura=self.fetch_config.prefer_trafilatura,
            firecrawl_api_key=self.fetch_config.firecrawl_api_key,
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return _web_research_parameters(self.search_config, self.fetch_config)

    async def execute_validated(self, params: Any) -> str:
        """Normalize common LLM query-object shapes before schema validation."""
        return await super().execute_validated(_normalize_research_params(params))

    async def _execute(
        self,
        query: str,
        count: int | None = None,
        fetch_count: int | None = None,
        freshness: str | None = None,
        max_chars: int | None = None,
        queries: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        (
            research_queries,
            effective_freshness,
            search_count,
            target_fetches,
            effective_max_chars,
        ) = _prepare_research_request(
            query=query,
            queries=queries,
            count=count,
            fetch_count=fetch_count,
            freshness=freshness,
            max_chars=max_chars,
            max_results=self.search_config.max_results,
            default_freshness=self.search_config.freshness,
            default_max_chars=self.fetch_config.max_chars,
        )
        fetched_sources: list[dict[str, Any]] = []
        failed_sources: list[dict[str, Any]] = []
        source_records: list[dict[str, Any]] = []
        fetched_urls: set[str] = set()

        search_items, search_provider, search_backend, search_attempts, query_attempts = await self._search_queries_with_fallback(
            queries=research_queries,
            count=search_count,
            freshness=effective_freshness,
        )
        (
            research_queries,
            search_items,
            search_provider,
            search_backend,
            search_attempts,
            query_attempts,
            official_domains,
        ) = await _apply_official_site_search(
            query=query,
            research_queries=research_queries,
            search_items=search_items,
            search_provider=search_provider,
            search_backend=search_backend,
            search_attempts=search_attempts,
            query_attempts=query_attempts,
            count=search_count,
            freshness=effective_freshness,
            search_queries=self._search_queries_with_fallback,
        )
        if not search_items:
            return _research_payload(
                query=query,
                freshness=effective_freshness,
                search_provider=search_provider,
                search_backend=search_backend,
                search_items=[],
                fetched_sources=fetched_sources,
                failed_sources=[{"reason": "web_search returned no structured result with fetchable URLs"}],
                sources=source_records,
                target_fetch_count=target_fetches,
                search_attempts=search_attempts,
                query_attempts=query_attempts,
                queries=research_queries,
            )

        fetched_by_candidate_url: dict[str, dict[str, Any]] = {}
        fetch_candidates = _prioritize_research_candidates(
            search_items,
            existing_sources=fetched_sources,
            freshness=effective_freshness,
            official_domains=official_domains,
        )
        fetch_candidates = _expand_llms_full_candidates(fetch_candidates)
        fetched_by_candidate_url = await self._fetch_research_candidates(
            candidates=fetch_candidates,
            fetched_sources=fetched_sources,
            failed_sources=failed_sources,
            fetched_urls=fetched_urls,
            target_fetches=target_fetches,
            max_chars=effective_max_chars,
            query=query,
            search_provider=search_provider,
            search_backend=search_backend,
        )

        source_records = _source_records_for_search_items(
            search_items,
            fetched_by_candidate_url=fetched_by_candidate_url,
            search_provider=search_provider,
            search_backend=search_backend,
        )

        return _research_payload(
            query=query,
            freshness=effective_freshness,
            search_provider=search_provider,
            search_backend=search_backend,
            search_items=search_items,
            fetched_sources=fetched_sources,
            failed_sources=failed_sources,
            sources=source_records,
            target_fetch_count=target_fetches,
            search_attempts=search_attempts,
            query_attempts=query_attempts,
            queries=research_queries,
        )

    async def _fetch_research_candidates(
        self,
        *,
        candidates: list[dict[str, Any]],
        fetched_sources: list[dict[str, Any]],
        failed_sources: list[dict[str, Any]],
        fetched_urls: set[str],
        target_fetches: int,
        max_chars: int,
        query: str,
        search_provider: str,
        search_backend: str,
    ) -> dict[str, dict[str, Any]]:
        return await _fetch_research_candidates_batch(
            candidates=candidates,
            fetched_sources=fetched_sources,
            failed_sources=failed_sources,
            fetched_urls=fetched_urls,
            target_fetches=target_fetches,
            max_chars=max_chars,
            query=query,
            search_provider=search_provider,
            search_backend=search_backend,
            fetch_candidate=self._fetch_single_candidate,
            fetch_concurrency=_WEB_RESEARCH_FETCH_CONCURRENCY,
        )

    async def _fetch_single_candidate(
        self,
        item: dict[str, Any],
        *,
        max_chars: int,
        query: str,
        search_provider: str,
        search_backend: str,
    ) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
        return await _fetch_single_research_candidate(
            self.fetch_tool,
            item,
            max_chars=max_chars,
            query=query,
            search_provider=search_provider,
            search_backend=search_backend,
        )

    async def _search_queries_with_fallback(
        self,
        *,
        queries: list[str],
        count: int,
        freshness: str,
    ) -> tuple[list[dict[str, Any]], str, str, list[dict[str, Any]], list[dict[str, Any]]]:
        return await _search_queries_with_fallback_batch(
            queries=queries,
            count=count,
            freshness=freshness,
            search_query=self._search_with_fallback,
            search_concurrency=_WEB_RESEARCH_SEARCH_CONCURRENCY,
        )

    async def _search_with_fallback(
        self,
        *,
        query: str,
        count: int,
        freshness: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str, str, list[dict[str, Any]]]:
        return await _search_with_fallback_helper(
            query=query,
            count=count,
            freshness=freshness,
            search_config=self.search_config,
            search_tool=self.search_tool,
            custom_search_tool=self._custom_search_tool,
        )
