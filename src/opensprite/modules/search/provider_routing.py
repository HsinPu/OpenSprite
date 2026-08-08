"""Provider dispatch helpers for web search."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ...core.contracts.web_search import (
    DEFAULT_WEB_SEARCH_PROVIDER as _DEFAULT_WEB_SEARCH_PROVIDER,
)


WebSearchProvider = Callable[[str, int, str], Awaitable[str]]


def normalize_web_search_provider(provider: str | None) -> str:
    return str(provider or "").strip().lower() or _DEFAULT_WEB_SEARCH_PROVIDER


def web_search_provider(
    provider: str,
    *,
    duckduckgo: WebSearchProvider,
    searxng: WebSearchProvider,
) -> WebSearchProvider | None:
    """Return the configured provider callable, if supported."""
    return {
        "duckduckgo": duckduckgo,
        "searxng": searxng,
    }.get(normalize_web_search_provider(provider))
