"""Fetch helpers for web research."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .web_research_search import parse_json_object
from .web_research_sources import merge_fetch_source
from .web_research_urls import candidate_url_key, clean_text, is_fetchable_url

FetchCandidate = Callable[..., Awaitable[tuple[str, dict[str, Any] | None, dict[str, Any] | None]]]


async def fetch_research_candidates(
    *,
    candidates: list[dict[str, Any]],
    fetched_sources: list[dict[str, Any]],
    failed_sources: list[dict[str, Any]],
    fetched_urls: set[str],
    target_fetches: int,
    max_chars: int,
    query: str,
    search_provider: str,
    search_backend: str,
    fetch_candidate: FetchCandidate,
    fetch_concurrency: int,
) -> dict[str, dict[str, Any]]:
    fetched_by_candidate_url: dict[str, dict[str, Any]] = {}
    cursor = 0
    while len(fetched_sources) < target_fetches and cursor < len(candidates):
        remaining_needed = max(target_fetches - len(fetched_sources), 1)
        batch_size = min(
            len(candidates) - cursor,
            max(remaining_needed, min(fetch_concurrency, max(target_fetches, 1))),
        )
        batch = candidates[cursor : cursor + batch_size]
        cursor += batch_size

        tasks: list[Any] = []
        for item in batch:
            url = clean_text(item.get("url"))
            if not url:
                failed_sources.append({**item, "reason": "missing url"})
                continue
            if not is_fetchable_url(url):
                failed_sources.append({**item, "reason": "unsupported url"})
                continue
            canonical_url = candidate_url_key(item)
            if canonical_url in fetched_urls:
                continue
            tasks.append(
                fetch_candidate(
                    item,
                    max_chars=max_chars,
                    query=query,
                    search_provider=search_provider,
                    search_backend=search_backend,
                )
            )

        if not tasks:
            continue

        for canonical_url, fetched, failed in await asyncio.gather(*tasks):
            if failed is not None:
                failed_sources.append(failed)
                continue
            if fetched is None:
                continue
            final_url_key = str(fetched.get("canonical_url") or fetched.get("url") or "")
            if final_url_key and final_url_key in fetched_urls and final_url_key != canonical_url:
                failed_sources.append({**fetched, "reason": "duplicate final url"})
                continue
            if fetched.get("blocked_or_challenge"):
                failed_sources.append({**fetched, "reason": "fetched content looked blocked or challenged"})
                continue
            if fetched.get("is_too_short") or not fetched.get("has_main_content"):
                failed_sources.append({**fetched, "reason": "fetched content was too short"})
                continue

            fetched_sources.append(fetched)
            fetched_by_candidate_url[canonical_url] = fetched
            fetched_urls.add(canonical_url)
            if final_url_key:
                fetched_urls.add(final_url_key)
            if len(fetched_sources) >= target_fetches:
                break

    return fetched_by_candidate_url


async def fetch_single_candidate(
    fetch_tool: Any,
    item: dict[str, Any],
    *,
    max_chars: int,
    query: str,
    search_provider: str,
    search_backend: str,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    canonical_url = candidate_url_key(item)
    url = clean_text(item.get("url"))
    item_search_provider = str(item.get("search_provider") or search_provider)
    item_search_backend = str(item.get("search_backend") or search_backend)
    try:
        fetch_result = await fetch_tool._execute(url=url, max_chars=max_chars)
    except Exception as exc:
        return canonical_url, None, {**item, "reason": f"web_fetch failed: {exc}"[:500]}
    fetch_payload = parse_json_object(fetch_result)
    if fetch_payload is None:
        return canonical_url, None, {
            **item,
            "reason": str(fetch_result or "web_fetch returned no structured result")[:500],
        }

    return canonical_url, merge_fetch_source(
        item,
        fetch_payload,
        query=str(item.get("source_query") or query),
        search_provider=item_search_provider,
        search_backend=item_search_backend,
    ), None
