"""Shared labels for LLM requests."""

from __future__ import annotations

from enum import Enum


class LLMRequestMode(str, Enum):
    """High-level reason a provider request is being made."""

    MAIN_CHAT = "main_chat"


def normalize_request_mode(mode: LLMRequestMode | str | None) -> str:
    """Return a stable request-mode label for logging and provider kwargs."""
    if isinstance(mode, LLMRequestMode):
        return mode.value
    return str(mode or LLMRequestMode.MAIN_CHAT.value).strip() or LLMRequestMode.MAIN_CHAT.value


def resolve_response_format(
    response_format: dict[str, object] | None,
    mode: LLMRequestMode | str | None,
) -> dict[str, object] | None:
    """Return an explicitly requested provider response format."""
    del mode
    return response_format
