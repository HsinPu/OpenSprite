"""Provider listing payload builders for settings APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .provider_choices import get_provider_model_choices
from .provider_discovery import discover_provider_models
from .provider_public import (
    public_available_provider,
    public_connected_provider,
    public_model_provider,
)
from .provider_state import connected_provider_entries
from .schema import Config


def build_provider_listing(
    *,
    config_path: Path,
    main_data: dict[str, Any],
    providers: dict[str, Any],
    loaded: Any,
    presets: Any,
) -> dict[str, Any]:
    """Return configured and available providers without leaking API keys."""
    default_provider = loaded.llm.default
    connected = [
        public_connected_provider(
            provider_id,
            provider,
            preset_id=preset_id,
            preset=preset,
            default_provider=default_provider,
            app_home=config_path.parent,
        )
        for provider_id, provider, preset_id, preset in connected_provider_entries(
            providers,
            presets,
        )
    ]
    available = [
        public_available_provider(provider_id, presets.providers[provider_id], connected)
        for provider_id in presets.provider_order
    ]
    return {
        "default_provider": default_provider,
        "connected": connected,
        "available": available,
        "restart_required": False,
        "config_path": str(config_path),
        "providers_file": str(Config.get_llm_providers_file_path(config_path, main_data.get("llm", {}))),
    }


def build_model_listing(
    *,
    config_path: Path,
    providers: dict[str, Any],
    loaded: Any,
    presets: Any,
) -> dict[str, Any]:
    """Return selectable models for connected providers."""
    out: list[dict[str, Any]] = []
    for provider_id, provider, preset_id, preset in connected_provider_entries(
        providers,
        presets,
    ):
        discovered_models, model_source, model_metadata = discover_provider_models(
            provider_id,
            provider,
            preset,
            app_home=config_path.parent,
        )
        choices, _ = get_provider_model_choices(provider, model_choices=discovered_models)
        out.append(
            public_model_provider(
                provider_id,
                provider,
                preset_id=preset_id,
                preset=preset,
                default_provider=loaded.llm.default,
                choices=choices,
                model_source=model_source,
                model_metadata=model_metadata,
            )
        )

    active = providers.get(loaded.llm.default or "", {}) if loaded.llm.default else {}
    active_model = active.get("model") if isinstance(active, dict) else None
    return {
        "default_provider": loaded.llm.default,
        "active_model": active_model or "",
        "providers": out,
        "restart_required": False,
    }
