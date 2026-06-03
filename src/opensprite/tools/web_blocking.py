"""Shared web access-blocking and challenge detection helpers."""

from __future__ import annotations

from typing import Any


BLOCKED_OR_CHALLENGE_STATUSES = frozenset({401, 403, 407, 408, 409, 429, 451, 503})
BLOCKED_OR_CHALLENGE_TEXT_MARKERS = (
    "captcha",
    "cloudflare",
    "access denied",
    "forbidden",
    "enable javascript",
    "verify you are human",
    "prove you are human",
    "unusual traffic",
    "too many requests",
)


def looks_blocked_or_challenge(*, title: str, content: str, status: Any) -> bool:
    """Return whether fetched web content looks like an access block or anti-bot challenge."""
    if _coerce_status(status) in BLOCKED_OR_CHALLENGE_STATUSES:
        return True
    normalized = f"{title}\n{content}".lower()
    return any(marker in normalized for marker in BLOCKED_OR_CHALLENGE_TEXT_MARKERS)


def _coerce_status(status: Any) -> int | None:
    try:
        return int(status)
    except (TypeError, ValueError):
        return None
