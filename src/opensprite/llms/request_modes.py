"""Shared request-mode policy for internal LLM calls."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class LLMRequestMode(str, Enum):
    """High-level reason a provider request is being made."""

    MAIN_CHAT = "main_chat"
    JSON_PLANNING = "json_planning"
    COMPLETION_VERIFIER = "completion_verifier"


JSON_PLANNING_MIN_OUTPUT_TOKENS = 1200
JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}
_JSON_ONLY_MODES = {LLMRequestMode.JSON_PLANNING, LLMRequestMode.COMPLETION_VERIFIER}


def normalize_request_mode(mode: LLMRequestMode | str | None) -> str:
    """Return a stable request-mode label for logging and provider kwargs."""
    if isinstance(mode, LLMRequestMode):
        return mode.value
    return str(mode or LLMRequestMode.MAIN_CHAT.value).strip() or LLMRequestMode.MAIN_CHAT.value


def request_mode_requires_json_response(mode: LLMRequestMode | str | None) -> bool:
    """Return whether a mode must ask the provider to enforce JSON output."""
    return normalize_request_mode(mode) in {item.value for item in _JSON_ONLY_MODES}


def response_format_for_request_mode(mode: LLMRequestMode | str | None) -> dict[str, Any] | None:
    """Return the provider response_format required by an internal request mode."""
    if request_mode_requires_json_response(mode):
        return dict(JSON_OBJECT_RESPONSE_FORMAT)
    return None


def resolve_response_format(
    response_format: dict[str, Any] | None,
    mode: LLMRequestMode | str | None,
) -> dict[str, Any] | None:
    """Prefer an explicit provider response_format, otherwise use request-mode policy."""
    if response_format is not None:
        return response_format
    return response_format_for_request_mode(mode)


def request_kwargs_for_mode(
    base_kwargs: Mapping[str, Any] | None,
    mode: LLMRequestMode | str | None,
    *,
    min_output_tokens: int = JSON_PLANNING_MIN_OUTPUT_TOKENS,
) -> dict[str, Any]:
    """Apply common request policy for an internal request mode."""
    kwargs = dict(base_kwargs or {})
    normalized = normalize_request_mode(mode)
    kwargs["request_mode"] = normalized

    if request_mode_requires_json_response(normalized):
        kwargs["max_tokens"] = _coerce_min_tokens(kwargs.get("max_tokens"), min_output_tokens)
        kwargs.setdefault("response_format", response_format_for_request_mode(normalized))

    return kwargs


def _coerce_min_tokens(value: Any, minimum: int) -> int:
    try:
        return max(int(value), int(minimum))
    except (TypeError, ValueError):
        return int(minimum)
