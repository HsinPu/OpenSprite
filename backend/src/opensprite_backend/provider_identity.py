"""Shared provider identity validation, separate from runtime availability."""

from typing import TypeAlias

from uuid import UUID


def require_provider_id(value: str) -> str:
    if value not in {"openai", "anthropic", "openrouter"}:
        try:
            parsed = UUID(value)
        except ValueError:
            raise ValueError("invalid_provider_id") from None
        if str(parsed) != value or parsed.version != 4:
            raise ValueError("invalid_provider_id")
    return value


ProviderId: TypeAlias = str
