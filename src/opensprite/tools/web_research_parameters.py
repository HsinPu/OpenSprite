"""Parameter schema helpers for web research."""

from __future__ import annotations

from typing import Any

from ..config.schema import WebFetchToolConfig, WebSearchToolConfig
from .validation import NON_EMPTY_STRING_PATTERN
from .web_search_freshness import FRESHNESS_VALUES


def web_research_parameters(
    search_config: WebSearchToolConfig,
    fetch_config: WebFetchToolConfig,
) -> dict[str, Any]:
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
                "default": search_config.max_results,
                "minimum": 1,
                "maximum": search_config.max_results,
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
                "default": search_config.freshness,
            },
            "max_chars": {
                "type": "integer",
                "description": "Max characters per fetched page",
                "default": fetch_config.max_chars,
                "minimum": 1,
            },
        },
        "required": ["query"],
    }
