"""In-memory provider config state helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth.credentials import DEFAULT_LLM_CAPABILITY, add_credential
from ..llms.reasoning import REASONING_EFFORT_OPTIONS, is_valid_reasoning_effort, normalize_reasoning_effort
from .json_files import load_json_dict
from .llm_presets import ProviderPreset, load_llm_presets
from .provider_auth_types import API_KEY_AUTH_TYPE
from .provider_choices import (
    get_configured_provider_id,
    get_provider_choices,
    get_provider_preset_id,
)
from .provider_credentials import has_provider_secret
from .provider_discovery import cached_openrouter_model_metadata, positive_int_or_none
from .provider_errors import (
    ProviderSettingsConflict,
    ProviderSettingsNotFound,
    ProviderSettingsValidationError,
)
from .schema import Config


def _validated_reasoning_effort(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if not is_valid_reasoning_effort(normalized):
        allowed = ", ".join(option or "default" for option in REASONING_EFFORT_OPTIONS)
        raise ProviderSettingsValidationError(f"reasoning_effort must be one of: {allowed}")
    return normalize_reasoning_effort(normalized)


def provider_config_to_settings_data(provider: Any) -> dict[str, Any]:
    """Dump provider config without persisting empty optional request settings."""
    data = provider.model_dump()
    if not data.get("reasoning_effort"):
        data.pop("reasoning_effort", None)
    return data


def load_provider_config_state(config_path: str | Path) -> tuple[dict[str, Any], dict[str, Any], Config]:
    path = Path(config_path).expanduser().resolve()
    if not path.exists():
        raise ProviderSettingsNotFound(f"Config file not found: {path}")
    main_data = load_json_dict(path)
    loaded = Config.from_json(path)
    providers = {name: provider_config_to_settings_data(provider) for name, provider in loaded.llm.providers.items()}
    return main_data, providers, loaded


def provider_mutation_sections(config_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the mutable llm/provider sections used by provider mutations."""
    llm = config_data.setdefault("llm", {})
    providers = llm.setdefault("providers", {})
    return llm, providers


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
        if isinstance(provider, dict) and has_provider_secret(provider):
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

    _, providers = provider_mutation_sections(config_data)
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
    elif preset.auth_type == API_KEY_AUTH_TYPE and not has_provider_secret(provider):
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

    llm, providers = provider_mutation_sections(config_data)
    provider = providers.get(provider_id)
    if not isinstance(provider, dict):
        raise ProviderSettingsConflict("Provider must be connected before selecting a model")
    provider, _, preset = provider_preset_entry(provider_id, provider, presets)
    if preset is None:
        raise ProviderSettingsNotFound(f"Unknown provider: {provider_id}")
    if require_api_key and preset.auth_type == API_KEY_AUTH_TYPE and not has_provider_secret(provider):
        raise ProviderSettingsConflict("Provider must be connected before selecting a model")

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
        context_length = positive_int_or_none(metadata.get("context_length"))
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
    if preset and preset.auth_type != API_KEY_AUTH_TYPE:
        return True
    return has_provider_secret(provider)


def provider_references_credential(
    provider_id: str,
    provider: dict[str, Any],
    *,
    credential_provider: str,
    credential_id: str,
) -> bool:
    """Return whether a provider instance references a stored credential."""
    return (
        get_configured_provider_id(provider_id, provider) == credential_provider
        and provider.get("credential_id") == credential_id
    )


def provider_preset_entry(provider_id: str, provider: Any, presets: Any) -> tuple[dict[str, Any], str | None, ProviderPreset | None]:
    provider_data = provider if isinstance(provider, dict) else {}
    preset_id = get_provider_preset_id(provider_id, provider_data, presets)
    preset = presets.providers.get(preset_id) if preset_id else None
    return provider_data, preset_id, preset


def connected_provider_entries(providers: dict[str, Any], presets: Any):
    for provider_id in get_provider_choices(
        {"llm": {"providers": providers}},
        provider_order=presets.provider_order,
    ):
        provider, preset_id, preset = provider_preset_entry(provider_id, providers.get(provider_id, {}), presets)
        if is_provider_connected(provider, preset):
            yield provider_id, provider, preset_id, preset


def connected_provider_or_raise(
    provider_id: str,
    providers: dict[str, Any],
    presets: Any,
) -> tuple[dict[str, Any], str | None, ProviderPreset | None]:
    provider = providers.get(provider_id)
    provider_data, preset_id, preset = provider_preset_entry(provider_id, provider, presets)
    if not isinstance(provider, dict) or not is_provider_connected(provider, preset):
        raise ProviderSettingsNotFound(f"Provider is not connected: {provider_id}")
    return provider_data, preset_id, preset


def clear_default_provider(main_data: dict[str, Any], providers: dict[str, Any]) -> None:
    main_data.setdefault("llm", {})["default"] = None
    for item in providers.values():
        if isinstance(item, dict):
            item["enabled"] = False


def provider_mutation_data(
    providers: dict[str, Any],
    default_provider: str | None,
    *,
    app_home: Any = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"llm": {"providers": providers, "default": default_provider}}
    if app_home is not None:
        data["app_home"] = app_home
    return data
