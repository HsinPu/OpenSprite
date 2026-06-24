"""High-level web research orchestration tool."""

from __future__ import annotations

from typing import Any

from ..config.defaults import DEFAULT_WEB_SEARCH_PROVIDER
from ..config.schema import WebFetchToolConfig, WebSearchToolConfig
from .base import Tool
from .validation import NON_EMPTY_STRING_PATTERN
from .web_fetch import WebFetchTool
from .web_research_candidates import (
    LOW_SIGNAL_DOMAIN_SUFFIXES as _LOW_SIGNAL_DOMAIN_SUFFIXES,
    MARKET_QUOTE_RULES as _MARKET_QUOTE_RULES,
    OFFICIAL_DOMAIN_STOPWORDS as _OFFICIAL_DOMAIN_STOPWORDS,
    MarketQuoteCandidateRules,
    candidate_low_signal_penalty as _candidate_low_signal_penalty,
    candidate_market_quote_penalty as _candidate_market_quote_penalty,
    candidate_official_penalty as _candidate_official_penalty,
    candidate_priority as _candidate_priority,
    candidate_recent_score as _candidate_recent_score,
    candidate_staleness_penalty as _candidate_staleness_penalty,
    dedupe_search_items as _dedupe_search_items,
    domain_brand_label as _domain_brand_label,
    expand_llms_full_candidates as _expand_llms_full_candidates,
    llms_full_url as _llms_full_url,
    market_quote_candidate_kind as _market_quote_candidate_kind,
    official_domain_hints as _official_domain_hints,
    prioritize_research_candidates as _prioritize_research_candidates,
)
from .web_research_urls import (
    candidate_domain as _candidate_domain,
    candidate_query as _candidate_query,
    candidate_url_key as _candidate_url_key,
    canonicalize_url as _canonicalize_url,
    clean_text as _clean_text,
    domain_from_url as _domain_from_url,
    domain_matches_any as _domain_matches_any,
    is_fetchable_url as _is_fetchable_url,
)
from .web_research_payloads import (
    ordered_clean_values as _ordered_clean_values,
    research_coverage as _research_coverage,
    research_payload as _research_payload,
    search_attempt_payload as _search_attempt_payload,
)
from .web_research_fetch import (
    fetch_research_candidates as _fetch_research_candidates_batch,
    fetch_single_candidate as _fetch_single_research_candidate,
)
from .web_research_queries import (
    MARKET_QUOTE_QUERY_RE as _MARKET_QUOTE_QUERY_RE,
    RECENT_FRESHNESS_VALUES as _RECENT_FRESHNESS_VALUES,
    YEAR_RE as _YEAR_RE,
    coerce_query_text as _coerce_query_text,
    dedupe_query_strings as _dedupe_query_strings,
    market_quote_entity_terms as _market_quote_entity_terms,
    market_quote_queries as _market_quote_queries,
    normalize_research_params as _normalize_research_params,
    official_site_queries as _official_site_queries,
    prefer_current_year_queries as _prefer_current_year_queries,
    research_queries as _research_queries,
    site_domain_hints as _site_domain_hints,
)
from .web_research_records import source_records_for_search_items as _source_records_for_search_items
from .web_research_search import (
    coerce_search_items as _coerce_search_items,
    dedupe_strings as _dedupe_strings,
    parse_json_object as _parse_json_object,
    apply_official_site_search as _apply_official_site_search,
    search_queries_with_fallback as _search_queries_with_fallback_batch,
    search_provider_order as _search_provider_order,
)
from .web_research_sources import (
    merge_fetch_source as _merge_fetch_source,
    quality_score as _quality_score,
)
from .web_search import FRESHNESS_VALUES, WebSearchTool, _effective_freshness

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
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research query", "pattern": NON_EMPTY_STRING_PATTERN},
                "queries": {
                    "type": "array",
                    "description": "Optional additional search queries to run and merge for broader research coverage",
                    "items": {"type": "string", "pattern": NON_EMPTY_STRING_PATTERN},
                    "maxItems": 5,
                },
                "count": {
                    "type": "integer",
                    "description": "Search candidates to inspect before dedupe; defaults to the configured max_results",
                    "default": self.search_config.max_results,
                    "minimum": 1,
                    "maximum": self.search_config.max_results,
                },
                "fetch_count": {
                    "type": "integer",
                    "description": "Number of substantive pages to fetch",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 5,
                },
                "freshness": {
                    "type": "string",
                    "enum": list(FRESHNESS_VALUES),
                    "description": "Recency filter passed through to web_search; auto uses the configured default recent window",
                    "default": self.search_config.freshness,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters per fetched page",
                    "default": self.fetch_config.max_chars,
                    "minimum": 1,
                },
            },
            "required": ["query"],
        }

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
        search_count = min(max(int(count or self.search_config.max_results), 1), self.search_config.max_results)
        target_fetches = min(max(int(fetch_count or 2), 1), 5)
        research_queries = _research_queries(query, queries)
        effective_freshness = _effective_freshness(
            freshness,
            self.search_config.freshness,
            query=" ".join(research_queries),
        )
        research_queries = _research_queries(query, queries, freshness=effective_freshness)
        effective_max_chars = max_chars if max_chars is not None else self.fetch_config.max_chars
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
        attempts: list[dict[str, Any]] = []
        last_provider = getattr(self.search_tool, "provider", self.search_config.provider)
        last_backend = ""
        if self._custom_search_tool:
            providers = [str(last_provider or self.search_config.provider or DEFAULT_WEB_SEARCH_PROVIDER)]
        else:
            providers = _search_provider_order(
                self.search_config,
                configured_provider=str(last_provider or ""),
            )
        for provider in providers:
            tool = self._search_tool_for_provider(provider)
            result = await tool._execute(query=query, count=count, freshness=freshness)
            payload = _parse_json_object(result)
            provider_name = str((payload or {}).get("provider") or getattr(tool, "provider", provider) or provider)
            backend_name = str((payload or {}).get("backend") or "")
            last_provider = provider_name
            last_backend = backend_name
            items = _dedupe_search_items(_coerce_search_items(payload or {}), limit=count) if payload else []
            fetchable_count = sum(1 for item in items if _is_fetchable_url(item.get("url")))
            attempts.append(
                _search_attempt_payload(
                    configured_provider=provider,
                    provider=provider_name,
                    backend=backend_name,
                    payload=payload,
                    items=items,
                    raw_result=result,
                    fetchable_count=fetchable_count,
                )
            )
            if payload is not None and fetchable_count > 0:
                return (
                    payload,
                    [
                        {
                            **item,
                            "search_provider": provider_name,
                            "search_backend": backend_name,
                            "search_freshness": str((payload or {}).get("freshness") or freshness),
                            "source_query": query,
                        }
                        for item in items
                    ],
                    provider_name,
                    backend_name,
                    attempts,
                )
        return None, [], str(last_provider or ""), str(last_backend or ""), attempts

    def _search_tool_for_provider(self, provider: str) -> WebSearchTool:
        if self._custom_search_tool:
            return self.search_tool
        if provider == self.search_tool.provider:
            return self.search_tool
        return WebSearchTool(config=self.search_config.model_copy(update={"provider": provider}))
