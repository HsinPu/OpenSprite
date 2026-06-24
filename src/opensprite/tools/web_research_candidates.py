"""Candidate ranking helpers for web research."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .web_research_queries import (
    MARKET_QUOTE_QUERY_RE,
    RECENT_FRESHNESS_VALUES,
    YEAR_RE,
    market_quote_entity_terms,
)
from .web_research_urls import (
    candidate_domain,
    candidate_query,
    clean_text,
    coerce_int,
    domain_matches_any,
    is_fetchable_url,
)

LOW_SIGNAL_DOMAIN_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "medium.com",
    "substack.com",
    "pinterest.com",
)
OFFICIAL_DOMAIN_STOPWORDS = {
    "api",
    "docs",
    "documentation",
    "official",
    "rate",
    "rates",
    "limit",
    "limits",
    "pricing",
    "tier",
    "tiers",
    "free",
    "paid",
}


@dataclass(frozen=True)
class MarketQuoteCandidateRules:
    preferred_domains: tuple[str, ...]
    discussion_domains: tuple[str, ...]
    forecast_domains: tuple[str, ...]
    forecast_markers: tuple[str, ...]
    quote_page_markers: tuple[str, ...]
    generic_quote_markers: tuple[str, ...]
    penalties: dict[str, int]


MARKET_QUOTE_RULES = MarketQuoteCandidateRules(
    preferred_domains=(
        "stock.yahoo.com",
        "finance.yahoo.com",
        "google.com",
        "cnyes.com",
        "wantgoo.com",
        "goodinfo.tw",
        "sinotrade.com.tw",
        "macromicro.me",
        "tradingview.com",
        "cnbc.com",
        "stockscan.io",
        "indmoney.com",
    ),
    discussion_domains=(
        "ptt.cc",
        "ptt.best",
        "reddit.com",
        "threads.com",
    ),
    forecast_domains=("blogspot.com",),
    forecast_markers=(
        "forecast",
        "prediction",
        "price target",
        "analyst target",
        "\u9810\u6e2c",
        "\u76ee\u6a19\u50f9",
    ),
    quote_page_markers=(
        "/quote/",
        "/quotes/",
        "/stocks/",
        "stock price",
        "share price",
        "live share price",
        "stock quote",
        "stock chart",
        "\u80a1\u5e02",
        "\u5831\u50f9",
    ),
    generic_quote_markers=("quote", "stock price", "\u80a1\u50f9", "\u5831\u50f9", "\u884c\u60c5"),
    penalties={
        "preferred": 0,
        "quote_page": 0,
        "generic_quote": 1,
        "other": 1,
        "forecast": 3,
        "discussion": 4,
    },
)


def dedupe_search_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("canonical_url") or item.get("url") or item.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def prioritize_research_candidates(
    items: list[dict[str, Any]],
    *,
    existing_sources: list[dict[str, Any]],
    freshness: str,
    official_domains: set[str] | None = None,
) -> list[dict[str, Any]]:
    if len(items) <= 1:
        return items
    official_domains = set(official_domains or set())
    ordered_items = sorted(
        enumerate(items),
        key=lambda pair: (candidate_priority(pair[1], freshness, official_domains=official_domains), pair[0]),
    )
    ordered = [item for _, item in ordered_items]
    if official_domains:
        official = [item for item in ordered if candidate_official_penalty(item, official_domains) == 0]
        non_official = [item for item in ordered if candidate_official_penalty(item, official_domains) != 0]
        return [*official, *non_official]
    item_queries = {candidate_query(item) for item in items}
    item_queries.discard("")
    if len(item_queries) <= 1:
        return ordered

    selected: list[dict[str, Any]] = []
    remaining = list(ordered)
    covered_domains = {candidate_domain(source) for source in existing_sources}
    covered_domains.discard("")
    covered_queries = {candidate_query(source) for source in existing_sources}
    covered_queries.discard("")

    def take_candidates(*, require_new_query: bool, require_new_domain: bool) -> None:
        nonlocal remaining
        next_remaining: list[dict[str, Any]] = []
        for item in remaining:
            query = candidate_query(item)
            domain = candidate_domain(item)
            query_is_new = bool(query) and query not in covered_queries
            domain_is_new = bool(domain) and domain not in covered_domains
            if (not require_new_query or query_is_new) and (not require_new_domain or domain_is_new):
                selected.append(item)
                if query:
                    covered_queries.add(query)
                if domain:
                    covered_domains.add(domain)
                continue
            next_remaining.append(item)
        remaining = next_remaining

    take_candidates(require_new_query=True, require_new_domain=True)
    take_candidates(require_new_query=False, require_new_domain=True)
    selected.extend(remaining)
    return selected


def expand_llms_full_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derived: list[dict[str, Any]] = []
    seen_derived_urls: set[str] = set()
    for item in items:
        full_url = llms_full_url(item)
        if not full_url or full_url in seen_derived_urls:
            continue
        seen_derived_urls.add(full_url)
        derived.append(
            {
                **item,
                "url": full_url,
                "canonical_url": full_url,
                "title": f"{clean_text(item.get('title')) or 'Documentation'} full documentation",
                "snippet": clean_text(item.get("snippet") or item.get("content")),
                "llms_full_derived_from": clean_text(item.get("url")),
            }
        )
    if not derived:
        return items
    return dedupe_search_items([*derived, *items], limit=len(derived) + len(items))


def llms_full_url(item: dict[str, Any]) -> str:
    url = clean_text(item.get("url"))
    if not url:
        return ""
    lowered = url.lower()
    if lowered.endswith("/llms-full.txt"):
        return ""
    if lowered.endswith("/llms.txt"):
        return f"{url[:-len('/llms.txt')]}/llms-full.txt"
    text = f"{url} {clean_text(item.get('title'))} {clean_text(item.get('snippet') or item.get('content'))}".lower()
    if "/llms-full.txt" not in text:
        return ""
    base = url.rstrip("/")
    if base.endswith("/docs"):
        return f"{base}/llms-full.txt"
    return ""


def candidate_priority(
    item: dict[str, Any],
    freshness: str,
    *,
    official_domains: set[str] | None = None,
) -> tuple[int, int, int, int, int, int, int]:
    fetchable_penalty = 0 if is_fetchable_url(item.get("url")) else 1
    quote_penalty = candidate_market_quote_penalty(item)
    official_penalty = candidate_official_penalty(item, official_domains or set())
    low_signal_penalty = candidate_low_signal_penalty(item)
    stale_penalty = candidate_staleness_penalty(item, freshness)
    recent_bonus = candidate_recent_score(item) if freshness in RECENT_FRESHNESS_VALUES else 0
    rank = coerce_int(item.get("rank"), default=9999)
    return (fetchable_penalty, quote_penalty, official_penalty, low_signal_penalty, stale_penalty, -recent_bonus, rank)


def candidate_market_quote_penalty(item: dict[str, Any]) -> int:
    query = candidate_query(item)
    if not MARKET_QUOTE_QUERY_RE.search(query):
        return 0
    domain = candidate_domain(item)
    text = " ".join(clean_text(item.get(key)).lower() for key in ("title", "content", "url", "domain"))
    query_terms = market_quote_entity_terms(query)
    if query_terms and not any(term in text for term in query_terms):
        return 2
    kind = market_quote_candidate_kind(domain=domain, text=text)
    return MARKET_QUOTE_RULES.penalties[kind]


def market_quote_candidate_kind(*, domain: str, text: str) -> str:
    """Classify quote-query candidates behind one searchable heuristic boundary."""
    rules = MARKET_QUOTE_RULES
    if domain_matches_any(domain, rules.discussion_domains):
        return "discussion"
    if domain_matches_any(domain, rules.forecast_domains):
        return "forecast"
    if any(marker in text for marker in rules.forecast_markers):
        return "forecast"
    if domain_matches_any(domain, rules.preferred_domains):
        return "preferred"
    if any(marker in text for marker in rules.quote_page_markers):
        return "quote_page"
    if any(marker in text for marker in rules.generic_quote_markers):
        return "generic_quote"
    return "other"


def official_domain_hints(query: str, items: list[dict[str, Any]]) -> set[str]:
    brand_tokens = {
        token.lower()
        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9]{2,}\b", str(query or ""))
        if token.lower() not in OFFICIAL_DOMAIN_STOPWORDS
    }
    if not brand_tokens:
        return set()

    hints: set[str] = set()
    for item in items:
        domain = candidate_domain(item)
        brand_label = domain_brand_label(domain)
        if any(token == brand_label for token in brand_tokens):
            hints.add(domain)
    return hints


def domain_brand_label(domain: str) -> str:
    labels = clean_text(domain).lower().removeprefix("www.").split(".")
    labels = [label for label in labels if label]
    if len(labels) < 2:
        return ""
    return labels[-2].replace("-", "")


def candidate_official_penalty(item: dict[str, Any], official_domains: set[str]) -> int:
    if not official_domains:
        return 0
    domain = candidate_domain(item)
    if any(domain == official or domain.endswith(f".{official}") for official in official_domains):
        return 0
    return 1


def candidate_recent_score(item: dict[str, Any]) -> int:
    text = " ".join(
        clean_text(item.get(key)).lower()
        for key in ("title", "content", "snippet", "url")
    )
    if not text:
        return 0
    current_year = str(datetime.now().year)
    score = 0
    if current_year in text:
        score += 4
    if re.search(r"\b20\d{2}[-/.](0?[1-9]|1[0-2])([-/.](0?[1-9]|[12]\d|3[01]))?\b", text):
        score += 2
    return score


def candidate_low_signal_penalty(item: dict[str, Any]) -> int:
    domain = candidate_domain(item)
    if not domain:
        return 0
    return 1 if any(domain == suffix or domain.endswith(f".{suffix}") for suffix in LOW_SIGNAL_DOMAIN_SUFFIXES) else 0


def candidate_staleness_penalty(item: dict[str, Any], freshness: str) -> int:
    if freshness not in RECENT_FRESHNESS_VALUES:
        return 0
    text = " ".join(
        clean_text(item.get(key)).lower()
        for key in ("title", "content", "snippet", "url", "source_query", "query")
    )
    if not text:
        return 0
    current_year = datetime.now().year
    years = [int(match) for match in YEAR_RE.findall(text)]
    if not years or current_year in years:
        return 0
    if max(years) < current_year:
        return 1
    return 0
