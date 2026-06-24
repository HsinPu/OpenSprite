"""Fetched source normalization helpers for web research."""

from __future__ import annotations

from typing import Any

from .web_blocking import looks_blocked_or_challenge
from .web_fetch import WEB_FETCH_MIN_CONTENT_CHARS
from .web_research_urls import canonicalize_url, clean_text, coerce_int, domain_from_url


def merge_fetch_source(
    item: dict[str, Any],
    fetch_payload: dict[str, Any],
    *,
    query: str,
    search_provider: str,
    search_backend: str,
) -> dict[str, Any]:
    url = clean_text(fetch_payload.get("final_url") or fetch_payload.get("finalUrl") or fetch_payload.get("url") or item.get("url"))
    content = str(fetch_payload.get("content") or fetch_payload.get("text") or "")
    content_chars = coerce_int(fetch_payload.get("content_chars"), default=len(content.strip()))
    min_content_chars = coerce_int(fetch_payload.get("min_content_chars"), default=WEB_FETCH_MIN_CONTENT_CHARS)
    title = clean_text(fetch_payload.get("title") or item.get("title"))
    status = fetch_payload.get("status")
    extractor = clean_text(fetch_payload.get("extractor"))
    truncated = bool(fetch_payload.get("truncated"))
    blocked_or_challenge = looks_blocked_or_challenge(title=title, content=content, status=status)
    is_too_short = bool(fetch_payload.get("is_too_short")) or content_chars < min_content_chars
    has_main_content = bool(content.strip()) and not is_too_short and not blocked_or_challenge
    source_quality_score = quality_score(
        content_chars=content_chars,
        min_content_chars=min_content_chars,
        has_title=bool(title),
        blocked_or_challenge=blocked_or_challenge,
        truncated=truncated,
        extractor=extractor,
    )
    source = {
        "rank": item.get("rank"),
        "title": title,
        "url": url,
        "canonical_url": canonicalize_url(url),
        "domain": domain_from_url(url),
        "snippet": clean_text(item.get("content")),
        "content": content,
        "content_chars": content_chars,
        "has_title": bool(title),
        "has_main_content": has_main_content,
        "is_too_short": is_too_short,
        "blocked_or_challenge": blocked_or_challenge,
        "quality_score": source_quality_score,
        "min_content_chars": min_content_chars,
        "truncated": truncated,
        "extractor": extractor,
        "status": status,
        "content_type": clean_text(fetch_payload.get("content_type") or fetch_payload.get("contentType")),
        "fetch_attempts": [
            {
                "tool": "web_fetch",
                "extractor": extractor,
                "status": status,
                "content_chars": content_chars,
                "is_too_short": is_too_short,
                "blocked_or_challenge": blocked_or_challenge,
                "quality_score": source_quality_score,
            }
        ],
        "source_query": query,
        "search_provider": search_provider,
        "search_backend": search_backend,
        "search_freshness": clean_text(item.get("search_freshness")),
        "search_rank": item.get("rank"),
    }
    derived_from = clean_text(item.get("llms_full_derived_from"))
    if derived_from:
        source["llms_full_derived_from"] = derived_from
    return source


def quality_score(
    *,
    content_chars: int,
    min_content_chars: int,
    has_title: bool,
    blocked_or_challenge: bool,
    truncated: bool,
    extractor: str,
) -> float:
    score = min(content_chars / max(min_content_chars, 1), 1.0) * 0.55
    if has_title:
        score += 0.15
    if not blocked_or_challenge:
        score += 0.15
    if extractor in {"trafilatura", "readability", "turndown", "jina", "firecrawl", "json"}:
        score += 0.10
    if not truncated:
        score += 0.05
    if blocked_or_challenge:
        score = min(score, 0.35)
    return round(min(max(score, 0.0), 1.0), 3)
