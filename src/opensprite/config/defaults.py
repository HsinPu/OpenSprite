"""Shared defaults used by config, settings APIs, and tool fallbacks."""

from __future__ import annotations

DEFAULT_WEB_SEARCH_PROVIDER = "duckduckgo"
WEB_SEARCH_PROVIDERS = ("duckduckgo", "brave", "tavily", "searxng", "jina")
DEFAULT_WEB_SEARCH_FRESHNESS = "year"
WEB_SEARCH_FRESHNESS_OPTIONS = ("none", "day", "week", "month", "year")
DEFAULT_SEARXNG_URL = "https://searx.be"
