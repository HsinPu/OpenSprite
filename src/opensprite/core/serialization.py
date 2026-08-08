"""Helpers for converting arbitrary metadata into JSON-safe shapes."""

from __future__ import annotations

from typing import Any


def json_safe_value(value: Any) -> Any:
    """Convert a value into JSON-serializable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(item) for item in value]
    return str(value)


def json_safe_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return a JSON-serializable metadata or event payload dictionary."""
    if not payload:
        return {}
    return {str(key): json_safe_value(value) for key, value in payload.items()}
