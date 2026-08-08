"""Web-fetch tool adapter."""

from __future__ import annotations

import asyncio
import json

from opensprite.integrations.web.fetcher import WebFetcher
from opensprite.modules.tools.base import Tool
from opensprite.modules.tools.validation import NON_EMPTY_STRING_PATTERN
from opensprite.modules.tools.web_access_policy import (
    looks_blocked_or_challenge as _looks_blocked_or_challenge,
)


WEB_FETCH_MIN_CONTENT_CHARS = 800


class WebFetchTool(Tool):
    """Tool-compatible wrapper around the HTTP content fetcher."""

    def __init__(
        self,
        max_chars: int = 50000,
        max_response_size: int = WebFetcher.DEFAULT_MAX_RESPONSE_SIZE,
        timeout: int = 30,
        prefer_trafilatura: bool = True,
        firecrawl_api_key: str | None = None,
    ):
        self.fetcher = WebFetcher(
            max_chars=max_chars,
            max_response_size=max_response_size,
            timeout=timeout,
            prefer_trafilatura=prefer_trafilatura,
            firecrawl_api_key=firecrawl_api_key,
        )

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch and extract readable content from a URL. Prefer this after selecting a specific source from web_search."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                    "pattern": NON_EMPTY_STRING_PATTERN,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters to return",
                    "default": self.fetcher.max_chars,
                    "minimum": 1,
                },
            },
            "required": ["url"],
        }

    async def _execute(self, url: str, max_chars: int | None = None, **kwargs: object) -> str:
        effective_max_chars = max_chars if max_chars is not None else self.fetcher.max_chars
        fetcher = WebFetcher(
            max_chars=effective_max_chars,
            max_response_size=self.fetcher.max_response_size,
            timeout=self.fetcher.timeout,
            prefer_trafilatura=self.fetcher.prefer_trafilatura,
            firecrawl_api_key=self.fetcher.firecrawl_api_key,
        )
        result = await asyncio.to_thread(fetcher.fetch, url)
        content = str(result.get("text") or "")
        content_chars = len(content.strip())
        raw_status = result.get("status")
        try:
            status = int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            status = None
        title = str(result.get("title") or "")
        blocked_or_challenge = _looks_blocked_or_challenge(title=title, content=content, status=status)
        is_too_short = content_chars < WEB_FETCH_MIN_CONTENT_CHARS
        has_main_content = bool(content.strip()) and not is_too_short and not blocked_or_challenge
        return json.dumps(
            {
                "type": "web_fetch",
                "query": url,
                "url": result.get("url"),
                "final_url": result.get("finalUrl"),
                "title": result.get("title"),
                "content": content,
                "summary": result.get("title") or result.get("url") or url,
                "provider": "web_fetch",
                "extractor": result.get("extractor"),
                "status": result.get("status"),
                "content_type": result.get("contentType"),
                "truncated": result.get("truncated"),
                "content_chars": content_chars,
                "has_title": bool(str(result.get("title") or "").strip()),
                "has_main_content": has_main_content,
                "is_too_short": is_too_short,
                "blocked_or_challenge": blocked_or_challenge,
                "min_content_chars": WEB_FETCH_MIN_CONTENT_CHARS,
                "items": [],
            },
            ensure_ascii=False,
        )
