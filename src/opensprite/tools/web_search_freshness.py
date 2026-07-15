"""Freshness policy shared by web search providers."""

from __future__ import annotations

from typing import Any

from ..config.defaults import WEB_SEARCH_FRESHNESS_OPTIONS


FRESHNESS_VALUES = WEB_SEARCH_FRESHNESS_OPTIONS
DUCKDUCKGO_FRESHNESS = {"day": "d", "week": "w", "month": "m", "year": "y"}
PROVIDER_FRESHNESS_PARAM_FIELDS = {"searxng": "time_range"}


def normalize_freshness(value: Any, default: str = "none") -> str:
    """Normalize tool/config freshness into a provider-agnostic value."""
    raw = str(value if value is not None else default).strip().lower()
    return raw if raw in FRESHNESS_VALUES else default


def web_search_request(
    *,
    count: Any,
    max_results: int,
    freshness: Any,
    default_freshness: str,
) -> tuple[int, str]:
    return (
        min(max(count or max_results, 1), max_results),
        normalize_freshness(freshness, default=default_freshness),
    )


def freshness_params(provider: str, freshness: str) -> dict[str, str]:
    """Return provider-specific recency parameters for supported engines."""
    normalized = normalize_freshness(freshness, default="none")
    if normalized == "none":
        return {}
    field = PROVIDER_FRESHNESS_PARAM_FIELDS.get(str(provider or "").strip().lower())
    if not field:
        return {}
    return {field: normalized}
