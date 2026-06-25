"""Public provider payload helpers for settings APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth.credentials import CredentialNotFoundError, list_credentials, resolve_credential
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


def public_credential_for_provider(
    provider_id: str,
    provider: dict[str, Any],
    preset_id: str | None,
    *,
    app_home: str | Path,
) -> dict[str, Any] | None:
    credential_id = str(provider.get("credential_id", "") or "").strip()
    if not credential_id and not preset_id:
        return None
    try:
        resolved = resolve_credential(
            provider=preset_id or provider_id,
            credential_id=credential_id or None,
            app_home=app_home,
        )
    except CredentialNotFoundError:
        return None
    credentials = list_credentials(resolved.provider, app_home=app_home).get(resolved.provider, [])
    return next((entry for entry in credentials if entry.get("id") == resolved.id), None)


def public_credential_source(provider: dict[str, Any], credential: dict[str, Any] | None) -> str:
    if not credential:
        return ""
    if str(provider.get("credential_id", "") or "").strip():
        return "explicit"
    if credential.get("is_default"):
        return "provider_default"
    return "priority"
