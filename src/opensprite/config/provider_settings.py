"""Shared provider/model settings helpers for Web settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth.credentials import set_provider_default
from .defaults import DEFAULT_LLM_PROVIDERS_FILE
from .json_files import write_json_dict
from .llm_presets import get_provider_profile, load_llm_presets
from .provider_choices import (
    get_configured_provider_id,
    get_model_choices,
    get_selected_provider,
    make_provider_instance_id,
)
from .provider_errors import (
    ProviderSettingsConflict,
    ProviderSettingsError,
    ProviderSettingsNotFound,
    ProviderSettingsValidationError,
)
from .provider_discovery import (
    discover_provider_models,
    fetch_codex_models,
    fetch_copilot_provider_models,
    fetch_openai_compatible_models,
    fetch_openrouter_image_models,
    fetch_openrouter_models,
)
from .provider_public import (
    public_available_provider,
    public_connected_provider,
    public_credential_for_provider,
    public_credential_source,
    public_model_provider,
    public_provider_auth_flags,
    public_provider_display_name,
    public_provider_identity,
    public_provider_profile,
)
from .provider_state import (
    clear_default_provider,
    connect_provider_in_config,
    connected_provider_entries,
    connected_provider_or_raise,
    load_provider_config_state,
    provider_mutation_data,
    select_model_in_config,
)
from .schema import Config


class ProviderSettingsService:
    """Read and mutate provider/model settings on disk."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).expanduser().resolve()

    def _load_state(self) -> tuple[dict[str, Any], dict[str, Any], Any]:
        return load_provider_config_state(self.config_path)

    def _persist_llm_state(self, main_data: dict[str, Any], providers: dict[str, Any]) -> None:
        llm_data = main_data.setdefault("llm", {})
        if not isinstance(llm_data, dict):
            raise ProviderSettingsValidationError("llm config must be an object")
        llm_data.pop("providers", None)
        llm_data.setdefault("providers_file", DEFAULT_LLM_PROVIDERS_FILE)
        write_json_dict(self.config_path, main_data)
        Config.ensure_llm_providers_file(self.config_path, main_data)
        Config.write_llm_providers_file(self.config_path, providers, llm_data)

    def list_providers(self) -> dict[str, Any]:
        """Return configured and available providers without leaking API keys."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        default_provider = loaded.llm.default
        connected: list[dict[str, Any]] = []

        for provider_id, provider, preset_id, preset in connected_provider_entries(
            providers,
            presets,
        ):
            connected.append(
                public_connected_provider(
                    provider_id,
                    provider,
                    preset_id=preset_id,
                    preset=preset,
                    default_provider=default_provider,
                    app_home=self.config_path.parent,
                )
            )

        available = [
            public_available_provider(provider_id, preset, connected)
            for provider_id in presets.provider_order
            for preset in [presets.providers[provider_id]]
        ]

        return {
            "default_provider": default_provider,
            "connected": connected,
            "available": available,
            "restart_required": False,
            "config_path": str(self.config_path),
            "providers_file": str(Config.get_llm_providers_file_path(self.config_path, main_data.get("llm", {}))),
        }

    def connect_provider(self, provider_id: str, *, api_key: str | None, base_url: str | None = None, name: str | None = None) -> dict[str, Any]:
        """Connect or update one provider without selecting a model."""
        main_data, providers, loaded = self._load_state()
        instance_id = make_provider_instance_id(provider_id, providers, name)
        config_data = provider_mutation_data(
            providers,
            loaded.llm.default,
            app_home=self.config_path.parent,
        )
        provider = connect_provider_in_config(
            config_data,
            instance_id,
            api_key=api_key,
            base_url=base_url,
            base_provider_id=provider_id,
            display_name=name,
        )
        self._persist_llm_state(main_data, providers)
        preset = get_provider_profile(provider_id)
        if preset is None:
            raise ProviderSettingsNotFound(f"Unknown provider: {provider_id}")
        return {
            "ok": True,
            "provider": public_connected_provider(
                instance_id,
                provider,
                preset_id=provider_id,
                preset=preset,
                default_provider=loaded.llm.default,
                app_home=self.config_path.parent,
            ),
            "restart_required": False,
        }

    def disconnect_provider(self, provider_id: str) -> dict[str, Any]:
        """Disconnect one provider, clearing the active model when needed."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        connected_provider_or_raise(provider_id, providers, presets)

        was_default = provider_id == loaded.llm.default
        providers.pop(provider_id, None)
        if was_default:
            clear_default_provider(main_data, providers)
        self._persist_llm_state(main_data, providers)
        return {"ok": True, "provider_id": provider_id, "restart_required": was_default}

    def set_provider_credential(self, provider_id: str, credential_id: str) -> dict[str, Any]:
        """Select which stored credential a connected provider instance should use."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        provider, preset_id, _preset = connected_provider_or_raise(
            provider_id,
            providers,
            presets,
        )
        credential = set_provider_default(
            preset_id or provider_id,
            credential_id,
            app_home=self.config_path.parent,
        )
        provider["credential_id"] = credential_id
        provider["api_key"] = ""
        self._persist_llm_state(main_data, providers)
        return {
            "ok": True,
            "provider_id": provider_id,
            "credential": credential,
            "restart_required": provider_id == loaded.llm.default,
        }

    def remove_credential_references(self, provider: str, credential_id: str) -> dict[str, Any]:
        """Remove provider instances that reference a deleted credential."""
        main_data, providers, loaded = self._load_state()
        removed_provider_ids: list[str] = []
        for provider_id, item in list(providers.items()):
            if not isinstance(item, dict):
                continue
            preset_id = get_configured_provider_id(provider_id, item)
            if preset_id != provider or item.get("credential_id") != credential_id:
                continue
            providers.pop(provider_id, None)
            removed_provider_ids.append(provider_id)
        restart_required = bool(loaded.llm.default in removed_provider_ids)
        if restart_required:
            clear_default_provider(main_data, providers)
        if removed_provider_ids:
            self._persist_llm_state(main_data, providers)
        return {
            "removed_provider_ids": removed_provider_ids,
            "restart_required": restart_required,
        }

    def list_models(self) -> dict[str, Any]:
        """Return selectable models for connected providers."""
        _, providers, loaded = self._load_state()
        presets = load_llm_presets()
        out: list[dict[str, Any]] = []
        for provider_id, provider, preset_id, preset in connected_provider_entries(
            providers,
            presets,
        ):
            discovered_models, model_source, model_metadata = discover_provider_models(
                provider_id,
                provider,
                preset,
                app_home=self.config_path.parent,
            )
            choices, _ = get_model_choices(
                str(provider.get("model") or "") or None,
                model_choices=tuple(discovered_models),
            )
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

    def select_model(self, provider_id: str, model: str, *, reasoning_effort: str | None = None) -> dict[str, Any]:
        """Select the active provider/model and persist it."""
        main_data, providers, _loaded = self._load_state()
        config_data = provider_mutation_data(
            providers,
            main_data.get("llm", {}).get("default"),
        )
        provider = select_model_in_config(config_data, provider_id, model, reasoning_effort=reasoning_effort)
        llm_data = main_data.setdefault("llm", {})
        llm_data["default"] = provider_id
        self._persist_llm_state(main_data, providers)
        return {
            "ok": True,
            "provider_id": provider_id,
            "model": str(model).strip(),
            "reasoning_effort": provider.get("reasoning_effort") or "",
            "restart_required": True,
        }
