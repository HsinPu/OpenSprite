"""Shared text and policy value helpers for task services."""

from __future__ import annotations

import re

_DEFAULT_TRUE_VALUES = frozenset({"1", "true", "yes", "y"})


def _compact_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _truncate_text(text: object, *, max_chars: int) -> str:
    compact = str(text or "").strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _truncate_middle_text(text: object, *, max_chars: int) -> str:
    compact = str(text or "").strip()
    if len(compact) <= max_chars:
        return compact
    if max_chars <= 20:
        return _truncate_text(compact, max_chars=max_chars)
    marker = "\n... [middle omitted] ...\n"
    remaining = max_chars - len(marker)
    head_chars = max(1, remaining // 2)
    tail_chars = max(1, remaining - head_chars)
    return f"{compact[:head_chars].rstrip()}{marker}{compact[-tail_chars:].lstrip()}"


def _policy_value(value: object) -> str:
    return str(value or "").strip()


def _allowed_policy_value(value: object, allowed: frozenset[str]) -> str | None:
    normalized = _policy_value(value)
    return normalized if normalized in allowed else None


def _coerce_policy_bool(
    value: object,
    *,
    truthy_values: frozenset[str] = _DEFAULT_TRUE_VALUES,
) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _policy_value(value).lower() in truthy_values


def _coerce_policy_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))
