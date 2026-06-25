"""Provider helpers for media settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .provider_choices import get_configured_provider_id
from .provider_credentials import resolve_provider_api_key


def get_provider_media_base_url(provider_id: str, provider: dict[str, Any]) -> str | None:
    """Return the media API base URL for a configured provider instance."""
    if get_configured_provider_id(provider_id, provider) == "minimax":
        return "https://api.minimax.io/v1"
    return provider.get("base_url")


def get_provider_media_config(
    provider_id: str,
    provider: dict[str, Any],
    *,
    app_home: str | Path | None = None,
) -> dict[str, Any]:
    """Return resolved media settings for a connected provider instance."""
    return {
        "provider": get_configured_provider_id(provider_id, provider),
        "api_key": resolve_provider_api_key(provider_id, provider, app_home=app_home),
        "base_url": get_provider_media_base_url(provider_id, provider),
    }
