"""In-memory provider config state helpers."""

from __future__ import annotations

from typing import Any

from ..auth.credentials import DEFAULT_LLM_CAPABILITY, add_credential
from ..llms.reasoning import REASONING_EFFORT_OPTIONS, is_valid_reasoning_effort, normalize_reasoning_effort
from .llm_presets import ProviderPreset, load_llm_presets
from .provider_choices import get_provider_preset_id
from .provider_discovery import _positive_int, cached_openrouter_model_metadata
from .provider_errors import (
    ProviderSettingsConflict,
    ProviderSettingsNotFound,
    ProviderSettingsValidationError,
)


def _validated_reasoning_effort(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if not is_valid_reasoning_effort(normalized):
        allowed = ", ".join(option or "default" for option in REASONING_EFFORT_OPTIONS)
        raise ProviderSettingsValidationError(f"reasoning_effort must be one of: {allowed}")
    return normalize_reasoning_effort(normalized)


def prune_llm_providers(llm: dict[str, Any]) -> None:
    """Keep the default provider and any configured providers; drop empty shells."""
    providers = llm.get("providers")
    if not isinstance(providers, dict):
        return
    default = llm.get("default")
    if not isinstance(default, str) or not default.strip():
        return
    default = default.strip()
    keep: set[str] = {default}
    for name, provider in providers.items():
        if isinstance(provider, dict) and (
            str(provider.get("api_key", "") or "").strip()
            or str(provider.get("credential_id", "") or "").strip()
        ):
            keep.add(name)
    llm["providers"] = {name: dict(providers[name]) for name in sorted(keep) if name in providers}


def ensure_provider_entry(
    providers: dict[str, Any],
    provider_id: str,
    preset: ProviderPreset,
) -> dict[str, Any]:
    """Ensure one provider entry exists and has baseline fields."""
    existing = providers.get(provider_id)
    if not isinstance(existing, dict):
        existing = {}
        providers[provider_id] = existing

    existing.setdefault("api_key", "")
    existing.setdefault("credential_id", "")
    existing.setdefault("model", "")
    existing.setdefault("base_url", preset.default_base_url)
    existing.setdefault("auth_type", preset.auth_type)
    if preset.api_mode:
        existing.setdefault("api_mode", preset.api_mode)
    existing.setdefault("enabled", False)
    if not str(existing.get("base_url", "") or "").strip():
        existing["base_url"] = preset.default_base_url
    return existing


def connect_provider_in_config(
    config_data: dict[str, Any],
    provider_id: str,
    *,
    api_key: str | None,
    base_url: str | None = None,
    base_provider_id: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Connect or update a provider inside an in-memory config object."""
    presets = load_llm_presets()
    preset_id = base_provider_id or provider_id
    if preset_id not in presets.providers:
        raise ProviderSettingsNotFound(f"Unknown provider: {preset_id}")

    llm = config_data.setdefault("llm", {})
    providers = llm.setdefault("providers", {})
    preset = presets.providers[preset_id]
    provider = ensure_provider_entry(providers, provider_id, preset)
    provider["provider"] = preset_id
    provider["auth_type"] = preset.auth_type
    if preset.api_mode:
        provider["api_mode"] = preset.api_mode
    normalized_name = str(display_name or "").strip()
    if normalized_name:
        provider["name"] = normalized_name

    normalized_key = str(api_key or "").strip()
    if normalized_key:
        credential = add_credential(
            preset_id,
            normalized_key,
            label=normalized_name or None,
            base_url=base_url or preset.default_base_url,
            scopes=[DEFAULT_LLM_CAPABILITY],
            app_home=config_data.get("app_home"),
        )
        provider["credential_id"] = credential["id"]
        provider["api_key"] = ""
    elif preset.auth_type == "api_key" and not (
        str(provider.get("api_key", "") or "").strip()
        or str(provider.get("credential_id", "") or "").strip()
    ):
        raise ProviderSettingsValidationError("api_key is required when connecting a new provider")

    normalized_base_url = str(base_url or "").strip()
    if normalized_base_url:
        provider["base_url"] = normalized_base_url
    elif not str(provider.get("base_url", "") or "").strip():
        provider["base_url"] = preset.default_base_url

    provider.setdefault("model", "")
    provider["enabled"] = bool(provider.get("enabled", False))
    return provider


def select_model_in_config(
    config_data: dict[str, Any],
    provider_id: str,
    model: str,
    *,
    require_api_key: bool = True,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Select the active provider/model inside an in-memory config object."""
    presets = load_llm_presets()
    normalized_model = str(model or "").strip()
    if not normalized_model:
        raise ProviderSettingsValidationError("model is required")

    llm = config_data.setdefault("llm", {})
    providers = llm.setdefault("providers", {})
    provider = providers.get(provider_id)
    if not isinstance(provider, dict):
        raise ProviderSettingsConflict("Provider must be connected before selecting a model")
    preset_id = get_provider_preset_id(provider_id, provider, presets)
    if preset_id is None:
        raise ProviderSettingsNotFound(f"Unknown provider: {provider_id}")
    if require_api_key and preset_id:
        preset = presets.providers[preset_id]
        if preset.auth_type == "api_key" and not (
            str(provider.get("api_key", "") or "").strip()
            or str(provider.get("credential_id", "") or "").strip()
        ):
            raise ProviderSettingsConflict("Provider must be connected before selecting a model")

    preset = presets.providers[preset_id]
    if not str(provider.get("base_url", "") or "").strip():
        provider["base_url"] = preset.default_base_url
    provider["model"] = normalized_model
    if reasoning_effort is not None:
        normalized_reasoning_effort = _validated_reasoning_effort(reasoning_effort)
        if normalized_reasoning_effort:
            provider["reasoning_effort"] = normalized_reasoning_effort
        else:
            provider.pop("reasoning_effort", None)
    if "model_metadata" in preset.capabilities:
        metadata = cached_openrouter_model_metadata([normalized_model]).get(normalized_model, {})
        context_length = _positive_int(metadata.get("context_length"))
        if context_length is not None:
            provider["context_window_tokens"] = context_length
        else:
            provider.pop("context_window_tokens", None)
    llm["default"] = provider_id
    for name, item in providers.items():
        if isinstance(item, dict):
            item["enabled"] = name == provider_id
    return provider


def is_provider_connected(provider: dict[str, Any], preset: ProviderPreset | None) -> bool:
    """Return whether a provider instance is configured enough for model selection."""
    if not isinstance(provider, dict):
        return False
    if not provider:
        return False
    if preset and preset.auth_type != "api_key":
        return True
    return bool(str(provider.get("api_key", "") or "").strip() or str(provider.get("credential_id", "") or "").strip())
