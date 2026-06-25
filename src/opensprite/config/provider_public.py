"""Public provider payload helpers for settings APIs."""

from __future__ import annotations

from typing import Any

from .llm_presets import ProviderPreset


def public_provider_display_name(
    provider_id: str,
    preset: ProviderPreset | None = None,
    provider: dict[str, Any] | None = None,
) -> str:
    configured_name = str((provider or {}).get("name", "") or "").strip()
    if configured_name:
        return configured_name
    if preset and preset.display_name:
        return preset.display_name
    return provider_id.replace("_", " ").replace("-", " ").title()


def public_provider_profile(preset: ProviderPreset | None) -> dict[str, Any]:
    """Return profile fields safe for settings APIs."""
    return {
        "capabilities": list(preset.capabilities) if preset else [],
        "model_metadata_fields": list(preset.model_metadata_fields) if preset else [],
    }


def public_provider_auth_flags(auth_type: str) -> dict[str, bool]:
    """Return auth requirement flags safe for settings APIs."""
    return {
        "requires_api_key": auth_type == "api_key",
        "api_key_optional": auth_type == "optional_api_key",
    }


def public_provider_identity(
    provider_id: str,
    provider: dict[str, Any],
    *,
    preset_id: str | None,
    preset: ProviderPreset | None,
    default_provider: str | None,
) -> dict[str, Any]:
    public_provider_id = preset_id or provider_id
    return {
        "id": provider_id,
        "provider": public_provider_id,
        "name": public_provider_display_name(provider_id, preset, provider),
        "preset_name": public_provider_display_name(public_provider_id, preset),
        "is_default": provider_id == default_provider,
        **public_provider_profile(preset),
    }
