"""Provider-neutral web search contracts."""

from __future__ import annotations


DEFAULT_WEB_SEARCH_PROVIDER = "duckduckgo"
WEB_SEARCH_PROVIDERS = ("duckduckgo", "searxng")
WEB_SEARCH_FRESHNESS_OPTIONS = ("none", "day", "week", "month", "year")
