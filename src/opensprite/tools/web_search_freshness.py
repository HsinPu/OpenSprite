"""Freshness policy shared by web search providers."""

from __future__ import annotations

from typing import Any

from ..config.defaults import WEB_SEARCH_FRESHNESS_OPTIONS


FRESHNESS_VALUES = WEB_SEARCH_FRESHNESS_OPTIONS
DUCKDUCKGO_FRESHNESS = {"day": "d", "week": "w", "month": "m", "year": "y"}
PROVIDER_FRESHNESS_PARAM_FIELDS = {"duckduckgo": "df", "jina": "df", "searxng": "time_range"}
AUTO_FRESHNESS = "month"


def normalize_freshness(value: Any, default: str = "year") -> str:
    """Normalize tool/config freshness into a provider-agnostic value."""
    raw = str(value if value is not None else default).strip().lower()
    aliases = {
        "": default,
        "all": "none",
        "any": "none",
        "off": "none",
        "false": "none",
        "today": "day",
        "d": "day",
        "daily": "day",
        "w": "week",
        "weekly": "week",
        "m": "month",
        "monthly": "month",
        "recent": "month",
        "latest": "month",
        "current": "month",
        "y": "year",
        "yearly": "year",
        "past_year": "year",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in FRESHNESS_VALUES else default


def effective_freshness(value: Any, default: str = "year", *, query: Any = None) -> str:
    """Resolve auto freshness while respecting explicit tool/config settings."""
    normalized = normalize_freshness(value, default)
    default_normalized = normalize_freshness(default, "year")
    if value is not None and normalized != "auto":
        return normalized
    if default_normalized != "auto":
        return normalized
    return AUTO_FRESHNESS


def web_search_request(
    *,
    query: str,
    count: Any,
    max_results: int,
    freshness: Any,
    default_freshness: str,
) -> tuple[int, str]:
    return (
        min(max(count or max_results, 1), max_results),
        effective_freshness(freshness, default_freshness, query=query),
    )


def freshness_params(provider: str, freshness: str) -> dict[str, str]:
    """Return provider-specific recency parameters for supported engines."""
    normalized = normalize_freshness(freshness, default="none")
    if normalized in {"auto", "none"}:
        return {}
    field = PROVIDER_FRESHNESS_PARAM_FIELDS.get(str(provider or "").strip().lower())
    if not field:
        return {}
    value = DUCKDUCKGO_FRESHNESS[normalized] if field == "df" else normalized
    return {field: value}
