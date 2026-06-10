"""Shared LLM reasoning-mode helpers."""

from __future__ import annotations

from typing import Any


VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
REASONING_EFFORT_OPTIONS = ("", "none", *VALID_REASONING_EFFORTS)


def normalize_reasoning_effort(effort: str | None) -> str:
    """Return a supported reasoning effort value, or empty for default provider behavior."""
    normalized = str(effort or "").strip().lower()
    return normalized if normalized in REASONING_EFFORT_OPTIONS else ""


def is_valid_reasoning_effort(effort: str | None) -> bool:
    """Return whether a reasoning effort value is accepted by config/settings APIs."""
    normalized = str(effort or "").strip().lower()
    return normalized in REASONING_EFFORT_OPTIONS


def reasoning_config_from_effort(effort: str | None) -> dict[str, Any] | None:
    """Convert a stored reasoning effort into the common reasoning config shape."""
    normalized = normalize_reasoning_effort(effort)
    if not normalized:
        return None
    if normalized == "none":
        return {"enabled": False}
    return {"enabled": True, "effort": normalized}
