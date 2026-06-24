"""URL and candidate helpers for web research."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def canonicalize_url(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    if not parsed.netloc:
        return str(url or "").strip().rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def domain_from_url(url: str) -> str:
    return urlsplit(str(url or "").strip()).netloc.lower()


def is_fetchable_url(url: Any) -> bool:
    parsed = urlsplit(clean_text(url))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def candidate_url_key(item: dict[str, Any]) -> str:
    return str(item.get("canonical_url") or canonicalize_url(str(item.get("url") or "")))


def candidate_domain(item: dict[str, Any]) -> str:
    return clean_text(item.get("domain") or domain_from_url(str(item.get("url") or ""))).lower()


def candidate_query(item: dict[str, Any]) -> str:
    return clean_text(item.get("source_query") or item.get("query")).lower()


def candidate_query_label(item: dict[str, Any]) -> str:
    return clean_text(item.get("source_query") or item.get("query"))


def domain_matches_any(domain: str, suffixes: tuple[str, ...]) -> bool:
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in suffixes)
