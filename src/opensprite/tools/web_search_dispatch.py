"""Provider dispatch helpers for web search."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..config.defaults import DEFAULT_WEB_SEARCH_PROVIDER


WebSearchProvider = Callable[[str, int, str], Awaitable[str]]


def normalize_web_search_provider(provider: str | None) -> str:
    return str(provider or "").strip().lower() or DEFAULT_WEB_SEARCH_PROVIDER


def web_search_provider(
    provider: str,
    *,
    duckduckgo: WebSearchProvider,
    searxng: WebSearchProvider,
    jina: WebSearchProvider,
) -> WebSearchProvider | None:
    """Return the configured provider callable, if supported."""
    return {
        "duckduckgo": duckduckgo,
        "searxng": searxng,
        "jina": jina,
    }.get(normalize_web_search_provider(provider))


def web_search_provider_order(
    configured_provider: str | None,
    *,
    searxng_available: bool = False,
    jina_available: bool = False,
) -> list[str]:
    candidates = [
        normalize_web_search_provider(configured_provider),
        "searxng" if searxng_available else "",
        "duckduckgo",
        "jina" if jina_available else "",
    ]
    return list(dict.fromkeys(provider for provider in candidates if provider))
