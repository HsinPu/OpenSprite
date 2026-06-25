"""Public provider payload helpers for settings APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth.credentials import CredentialNotFoundError, list_credentials, resolve_credential
from .llm_presets import ProviderPreset
from .provider_credentials import has_provider_secret


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


def public_connected_provider(
    provider_id: str,
    provider: dict[str, Any],
    *,
    preset_id: str | None,
    preset: ProviderPreset | None,
    default_provider: str | None,
    app_home: str | Path,
) -> dict[str, Any]:
    credential = public_credential_for_provider(provider_id, provider, preset_id, app_home=app_home)
    auth_type = preset.auth_type if preset else "api_key"
    return {
        **public_provider_identity(
            provider_id,
            provider,
            preset_id=preset_id,
            preset=preset,
            default_provider=default_provider,
        ),
        "base_url": provider.get("base_url") or (preset.default_base_url if preset else None),
        "model": provider.get("model") or "",
        "reasoning_effort": provider.get("reasoning_effort") or "",
        "api_key_configured": has_provider_secret(provider),
        "credential_id": provider.get("credential_id") or "",
        "credential_effective_id": (credential or {}).get("id") or "",
        "credential_source": public_credential_source(provider, credential),
        "credential_label": (credential or {}).get("label") or "",
        "credential_preview": (credential or {}).get("secret_preview") or "",
        "auth_type": provider.get("auth_type") or auth_type,
        **public_provider_auth_flags(auth_type),
        "enabled": bool(provider.get("enabled")),
    }


def public_available_provider(
    provider_id: str,
    preset: ProviderPreset,
    connected: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": provider_id,
        "name": public_provider_display_name(provider_id, preset),
        "default_base_url": preset.default_base_url,
        "auth_type": preset.auth_type,
        "api_mode": preset.api_mode,
        **public_provider_auth_flags(preset.auth_type),
        **public_provider_profile(preset),
        "model_choices": list(preset.model_choices),
        "connected_count": sum(
            1 for provider in connected if provider.get("provider") == provider_id
        ),
    }


def public_model_provider(
    provider_id: str,
    provider: dict[str, Any],
    *,
    preset_id: str | None,
    preset: ProviderPreset | None,
    default_provider: str | None,
    choices: list[str],
    model_source: str,
    model_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        **public_provider_identity(
            provider_id,
            provider,
            preset_id=preset_id,
            preset=preset,
            default_provider=default_provider,
        ),
        "is_connected": True,
        "selected_model": provider.get("model") or "",
        "reasoning_effort": provider.get("reasoning_effort") or "",
        "models": choices,
        "model_source": model_source,
        "model_metadata": {
            model: dict(metadata)
            for model, metadata in model_metadata.items()
            if model in choices and metadata
        },
        "model_capabilities": (
            (preset.model_capabilities or {}) if preset else {}
        ),
        "supports_custom_model": True,
    }


def public_media_provider(
    provider_id: str,
    provider: dict[str, Any],
    *,
    preset_id: str | None,
    preset: ProviderPreset | None,
    choices: list[str],
    selected: str,
    media_models: dict[str, list[str]],
    media_model_source: str,
) -> dict[str, Any]:
    return {
        "id": provider_id,
        "provider": preset_id or provider_id,
        "name": (
            public_provider_display_name(provider_id, preset, provider)
            if preset
            else str(provider.get("name") or "").strip() or provider_id
        ),
        "model": selected or "",
        "models": choices,
        "media_models": media_models,
        "media_model_source": media_model_source,
    }
