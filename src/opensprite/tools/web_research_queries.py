"""Query planning helpers for web research."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .web_research_urls import clean_text

RECENT_FRESHNESS_VALUES = {"day", "week", "month"}
YEAR_RE = re.compile(r"(?<!\d)20\d{2}(?!\d)")
MARKET_QUOTE_QUERY_RE = re.compile(
    r"\b(?:stock price|share price|quote|quotes|market price|ticker)\b"
    r"|(?:\u80a1\u50f9|\u5831\u50f9|\u5373\u6642\u884c\u60c5|\u76ee\u524d\u80a1\u50f9|\u4eca\u65e5\u80a1\u50f9)",
    re.IGNORECASE,
)
MARKET_QUOTE_QUERY_STOPWORDS = {
    "adr",
    "finance",
    "latest",
    "market",
    "price",
    "quote",
    "quotes",
    "share",
    "stock",
    "today",
    "yahoo",
    "\u6700\u65b0",
    "\u76ee\u524d",
    "\u4eca\u65e5",
    "\u5373\u6642",
    "\u80a1\u50f9",
    "\u80a1\u7968",
    "\u5831\u50f9",
    "\u884c\u60c5\u5831\u50f9",
}


def research_queries(query: str, queries: list[str] | None, *, freshness: str | None = None) -> list[str]:
    values = [clean_text(query)]
    if isinstance(queries, list):
        values.extend(clean_text(value) for value in queries[:5])
    elif queries is not None:
        values.append(clean_text(queries))
    values.extend(market_quote_queries(query))

    out = dedupe_query_strings(values)
    out = out or [clean_text(query)]
    return prefer_current_year_queries(out, freshness=freshness)


def prefer_current_year_queries(queries: list[str], *, freshness: str | None) -> list[str]:
    if freshness not in RECENT_FRESHNESS_VALUES:
        return queries
    combined = " ".join(clean_text(value).lower() for value in queries)
    current_year = datetime.now().year
    stale_years = sorted(
        {
            int(match)
            for match in YEAR_RE.findall(combined)
            if int(match) < current_year
        }
    )
    if not stale_years:
        return queries

    corrected: list[str] = []
    for query in queries:
        updated = query
        for year in stale_years:
            updated = re.sub(rf"(?<!\d){year}(?!\d)", str(current_year), updated)
        if updated != query:
            corrected.append(updated)

    return dedupe_query_strings([*corrected, *queries])


def market_quote_queries(query: str) -> list[str]:
    text = clean_text(query)
    if not text or not MARKET_QUOTE_QUERY_RE.search(text):
        return []
    queries = [f"{text} Yahoo Finance", f"{text} Yahoo \u80a1\u5e02"]
    terms = market_quote_entity_terms(text)
    if {"tsmc", "\u53f0\u7a4d\u96fb", "2330"} & terms:
        queries.extend(
            [
                "TSM quote Yahoo Finance",
                "2330.TW quote Yahoo Finance",
                "2330 \u53f0\u7a4d\u96fb Yahoo \u80a1\u5e02",
            ]
        )
    return queries


def market_quote_entity_terms(query: str) -> set[str]:
    text = clean_text(query).lower()
    terms: set[str] = set()
    for token in re.findall(r"\b[a-z][a-z0-9.:-]{1,}\b", text):
        if token in MARKET_QUOTE_QUERY_STOPWORDS or token.isdigit() or YEAR_RE.fullmatch(token):
            continue
        terms.add(token)
    for token in re.findall(r"\b\d{3,6}(?:\.[a-z]{1,4})?\b", text):
        if not YEAR_RE.fullmatch(token):
            terms.add(token)
    for token in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if token not in MARKET_QUOTE_QUERY_STOPWORDS:
            terms.add(token)
    if "tsmc" in terms or "\u53f0\u7a4d\u96fb" in terms or "2330" in terms:
        terms.update({"tsm", "tsmc", "taiwan semiconductor", "\u53f0\u7a4d\u96fb", "2330", "2330.tw"})
    return terms


def site_domain_hints(queries: list[str]) -> set[str]:
    hints: set[str] = set()
    for query in queries:
        for match in re.findall(r"\bsite:([A-Za-z0-9.-]+\.[A-Za-z]{2,})", str(query or ""), flags=re.IGNORECASE):
            domain = clean_text(match).lower().strip(".")
            if domain:
                hints.add(domain)
    return hints


def official_site_queries(query: str, official_domains: set[str], *, existing_queries: list[str]) -> list[str]:
    if not official_domains:
        return []
    existing = {value.lower() for value in existing_queries}
    out: list[str] = []
    for domain in sorted(official_domains)[:2]:
        site_query = f"site:{domain} {clean_text(query)}"
        key = site_query.lower()
        if key not in existing:
            out.append(site_query)
    return out


def dedupe_query_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = clean_text(value)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def normalize_research_params(params: Any) -> Any:
    if not isinstance(params, dict):
        return params
    normalized = dict(params)
    query = coerce_query_text(normalized.get("query"))
    raw_queries = normalized.get("queries")
    queries = [coerce_query_text(item) for item in raw_queries] if isinstance(raw_queries, list) else []
    queries = [item for item in queries if item]
    if query:
        normalized["query"] = query
    elif queries:
        normalized["query"] = queries[0]
        queries = queries[1:]
    if isinstance(raw_queries, list):
        normalized["queries"] = queries
    return normalized


def coerce_query_text(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, dict):
        for key in ("query", "q", "text", "title"):
            text = clean_text(value.get(key))
            if text:
                return text
    return ""
