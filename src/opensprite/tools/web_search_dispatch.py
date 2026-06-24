"""Provider dispatch helpers for web search."""

from __future__ import annotations

from collections.abc import Awaitable, Callable


WebSearchProvider = Callable[[str, int, str], Awaitable[str]]


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
    }.get(provider)
