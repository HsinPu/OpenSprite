"""Provider selection and model choice helpers."""

from __future__ import annotations

import re
from typing import Any


def get_selected_provider(config_data: dict[str, Any], *, provider_order: tuple[str, ...]) -> str | None:
    """Return the currently selected provider, if valid."""
    llm = config_data.get("llm", {})
    providers = llm.get("providers", {}) if isinstance(llm, dict) else {}
    default = llm.get("default") if isinstance(llm, dict) else None
    if isinstance(default, str) and default in providers:
        return default

    for provider_name in provider_order:
        provider = providers.get(provider_name, {}) if isinstance(providers, dict) else {}
        if isinstance(provider, dict) and (provider.get("enabled") or provider.get("api_key") or provider.get("credential_id")):
            return provider_name
    return None


def get_provider_choices(config_data: dict[str, Any], *, provider_order: tuple[str, ...]) -> list[str]:
    """Build a stable provider selection list."""
    providers = config_data.get("llm", {}).get("providers", {})
    order_set = set(provider_order)
    ordered = list(provider_order)
    extras = sorted(name for name in providers if name not in order_set)
    return ordered + extras


def get_model_choices(
    current_model: str | None,
    *,
    model_choices: tuple[str, ...],
    custom_choice: str | None = None,
) -> tuple[list[str], str | None]:
    """Return model choices and the default selection for a provider."""
    choices = list(model_choices)
    if current_model and current_model not in choices:
        choices.insert(0, current_model)
    if custom_choice and custom_choice not in choices:
        choices.append(custom_choice)
    default = current_model or (choices[0] if choices else None)
    return choices, default


def get_provider_preset_id(provider_id: str, provider: dict[str, Any], presets: Any) -> str | None:
    """Return the base preset id for a configured provider instance."""
    configured = str(provider.get("provider", "") or "").strip()
    if configured in presets.providers:
        return configured
    if provider_id in presets.providers:
        return provider_id
    return None


def make_provider_instance_id(base_provider_id: str, providers: dict[str, Any], display_name: str | None = None) -> str:
    """Create a stable id for an additional provider connection."""
    if base_provider_id not in providers:
        return base_provider_id
    slug_source = str(display_name or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug_source).strip("_")
    if slug:
        candidate = f"{base_provider_id}_{slug}"
        if candidate not in providers:
            return candidate
    index = 2
    while f"{base_provider_id}_{index}" in providers:
        index += 1
    return f"{base_provider_id}_{index}"
