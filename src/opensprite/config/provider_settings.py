"""Shared provider/model settings helpers for Web settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth.credentials import CredentialNotFoundError, list_credentials, resolve_credential, set_provider_default
from .defaults import DEFAULT_LLM_PROVIDERS_FILE
from .json_files import load_json_dict, write_json_dict
from .llm_presets import ProviderPreset, get_provider_profile, load_llm_presets
from .provider_choices import (
    get_model_choices,
    get_provider_choices,
    get_provider_preset_id,
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
    public_provider_auth_flags,
    public_provider_display_name,
    public_provider_identity,
    public_provider_profile,
)
from .provider_state import (
    connect_provider_in_config,
    ensure_provider_entry,
    is_provider_connected,
    prune_llm_providers,
    select_model_in_config,
)
from .schema import Config


def public_credential_for_provider(provider_id: str, provider: dict[str, Any], preset_id: str | None, *, app_home: str | Path) -> dict[str, Any] | None:
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


def provider_config_to_settings_data(provider: Any) -> dict[str, Any]:
    """Dump provider config without persisting empty optional request settings."""
    data = provider.model_dump()
    if not data.get("reasoning_effort"):
        data.pop("reasoning_effort", None)
    return data


class ProviderSettingsService:
    """Read and mutate provider/model settings on disk."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).expanduser().resolve()

    def _load_main_data(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise ProviderSettingsNotFound(f"Config file not found: {self.config_path}")
        return load_json_dict(self.config_path)

    def _load_state(self) -> tuple[dict[str, Any], dict[str, Any], Any]:
        main_data = self._load_main_data()
        loaded = Config.from_json(self.config_path)
        providers = {name: provider_config_to_settings_data(provider) for name, provider in loaded.llm.providers.items()}
        return main_data, providers, loaded

    def _persist_llm_state(self, main_data: dict[str, Any], providers: dict[str, Any]) -> None:
        llm_data = main_data.setdefault("llm", {})
        if not isinstance(llm_data, dict):
            raise ProviderSettingsValidationError("llm config must be an object")
        llm_data.pop("providers", None)
        llm_data.setdefault("providers_file", DEFAULT_LLM_PROVIDERS_FILE)
        write_json_dict(self.config_path, main_data)
        Config.ensure_llm_providers_file(self.config_path, main_data)
        Config.write_llm_providers_file(self.config_path, providers, llm_data)

    def _public_connected_provider(
        self,
        provider_id: str,
        provider: dict[str, Any],
        *,
        preset_id: str | None,
        preset: ProviderPreset | None,
        default_provider: str | None,
    ) -> dict[str, Any]:
        credential = public_credential_for_provider(provider_id, provider, preset_id, app_home=self.config_path.parent)
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
            "api_key_configured": bool(provider.get("api_key") or provider.get("credential_id")),
            "credential_id": provider.get("credential_id") or "",
            "credential_effective_id": (credential or {}).get("id") or "",
            "credential_source": public_credential_source(provider, credential),
            "credential_label": (credential or {}).get("label") or "",
            "credential_preview": (credential or {}).get("secret_preview") or "",
            "auth_type": provider.get("auth_type") or auth_type,
            **public_provider_auth_flags(auth_type),
            "enabled": bool(provider.get("enabled")),
        }

    def _public_available_provider(
        self,
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

    def _public_model_provider(
        self,
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

    def _connected_provider_entries(self, providers: dict[str, Any], presets: Any):
        for provider_id in get_provider_choices(
            {"llm": {"providers": providers}},
            provider_order=presets.provider_order,
        ):
            provider = providers.get(provider_id, {})
            preset_id = get_provider_preset_id(provider_id, provider, presets)
            preset = presets.providers.get(preset_id) if preset_id else None
            if is_provider_connected(provider, preset):
                yield provider_id, provider, preset_id, preset

    def _connected_provider_or_raise(
        self,
        provider_id: str,
        providers: dict[str, Any],
        presets: Any,
    ) -> tuple[dict[str, Any], str | None, ProviderPreset | None]:
        provider = providers.get(provider_id)
        preset_id = get_provider_preset_id(
            provider_id,
            provider if isinstance(provider, dict) else {},
            presets,
        )
        preset = presets.providers.get(preset_id) if preset_id else None
        if not isinstance(provider, dict) or not is_provider_connected(provider, preset):
            raise ProviderSettingsNotFound(f"Provider is not connected: {provider_id}")
        return provider, preset_id, preset

    @staticmethod
    def _clear_default_provider(main_data: dict[str, Any], providers: dict[str, Any]) -> None:
        main_data.setdefault("llm", {})["default"] = None
        for item in providers.values():
            if isinstance(item, dict):
                item["enabled"] = False

    def _provider_mutation_data(
        self,
        providers: dict[str, Any],
        default_provider: str | None,
        *,
        include_app_home: bool = False,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"llm": {"providers": providers, "default": default_provider}}
        if include_app_home:
            data["app_home"] = self.config_path.parent
        return data

    def list_providers(self) -> dict[str, Any]:
        """Return configured and available providers without leaking API keys."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        default_provider = loaded.llm.default
        connected: list[dict[str, Any]] = []

        for provider_id, provider, preset_id, preset in self._connected_provider_entries(
            providers,
            presets,
        ):
            connected.append(
                self._public_connected_provider(
                    provider_id,
                    provider,
                    preset_id=preset_id,
                    preset=preset,
                    default_provider=default_provider,
                )
            )

        available = [
            self._public_available_provider(provider_id, preset, connected)
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
        config_data = self._provider_mutation_data(
            providers,
            loaded.llm.default,
            include_app_home=True,
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
            "provider": self._public_connected_provider(
                instance_id,
                provider,
                preset_id=provider_id,
                preset=preset,
                default_provider=loaded.llm.default,
            ),
            "restart_required": False,
        }

    def disconnect_provider(self, provider_id: str) -> dict[str, Any]:
        """Disconnect one provider, clearing the active model when needed."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        self._connected_provider_or_raise(provider_id, providers, presets)

        was_default = provider_id == loaded.llm.default
        providers.pop(provider_id, None)
        if was_default:
            self._clear_default_provider(main_data, providers)
        self._persist_llm_state(main_data, providers)
        return {"ok": True, "provider_id": provider_id, "restart_required": was_default}

    def set_provider_credential(self, provider_id: str, credential_id: str) -> dict[str, Any]:
        """Select which stored credential a connected provider instance should use."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        provider, preset_id, _preset = self._connected_provider_or_raise(
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
            preset_id = str(item.get("provider") or provider_id or "").strip()
            if preset_id != provider or item.get("credential_id") != credential_id:
                continue
            providers.pop(provider_id, None)
            removed_provider_ids.append(provider_id)
        restart_required = bool(loaded.llm.default in removed_provider_ids)
        if restart_required:
            self._clear_default_provider(main_data, providers)
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
        for provider_id, provider, preset_id, preset in self._connected_provider_entries(
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
                self._public_model_provider(
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
        config_data = self._provider_mutation_data(
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
