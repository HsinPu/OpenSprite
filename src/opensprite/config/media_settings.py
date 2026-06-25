"""Shared media model settings helpers for Web settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .json_files import load_json_dict
from .llm_presets import load_llm_presets
from .provider_choices import get_provider_model_choices
from .provider_errors import (
    ProviderSettingsNotFound,
    ProviderSettingsValidationError,
)
from .provider_credentials import resolve_provider_api_key
from .provider_discovery import discover_media_model_choices
from .provider_media import get_provider_media_config
from .provider_public import public_media_provider
from .provider_state import connected_provider_entries, load_provider_config_state
from .schema import Config, OcrConfig, SpeechConfig, VideoConfig, VisionConfig


MEDIA_SECTIONS = {
    "vision": VisionConfig,
    "ocr": OcrConfig,
    "speech": SpeechConfig,
    "video": VideoConfig,
}


class MediaSettingsService:
    """Read and mutate media model settings on disk."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).expanduser().resolve()

    def _load_state(self) -> tuple[dict[str, Any], dict[str, Any], Config]:
        return load_provider_config_state(self.config_path)

    def _section_payload(self, category: str, config: Any, providers: dict[str, Any]) -> dict[str, Any]:
        return {
            "category": category,
            "enabled": bool(config.enabled),
            "provider": config.provider,
            "provider_id": self._section_provider_id(config, providers),
            "model": config.model,
            "base_url": config.base_url,
            "api_key_configured": bool(config.api_key),
        }

    def _section_provider_id(self, config: Any, providers: dict[str, Any]) -> str:
        expected_api_key = str(config.api_key or "")
        expected_base_url = str(config.base_url or "")
        for candidate_id, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            media_config = get_provider_media_config(
                candidate_id,
                provider,
                app_home=self.config_path.parent,
            )
            if (
                media_config["api_key"] == expected_api_key
                and str(media_config["base_url"] or "") == expected_base_url
                and media_config["provider"] == config.provider
            ):
                return candidate_id
        return ""

    def _provider_choice_payload(
        self,
        provider_id: str,
        provider: dict[str, Any],
        preset_id: str | None,
        preset: Any,
    ) -> dict[str, Any] | None:
        if not resolve_provider_api_key(provider_id, provider, app_home=self.config_path.parent):
            return None
        choices, selected = get_provider_model_choices(
            provider,
            model_choices=preset.model_choices if preset else (),
        )
        media_models, media_model_source = discover_media_model_choices(preset)
        return public_media_provider(
            provider_id,
            provider,
            preset_id=preset_id,
            preset=preset,
            choices=choices,
            selected=selected or "",
            media_models=media_models,
            media_model_source=media_model_source,
        )

    def _enabled_section_update(
        self,
        provider_id: str | None,
        model: str | None,
        providers: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_provider_id = str(provider_id or "").strip()
        normalized_model = str(model or "").strip()
        if not normalized_provider_id:
            raise ProviderSettingsValidationError(
                "provider_id is required when media model is enabled"
            )
        if not normalized_model:
            raise ProviderSettingsValidationError(
                "model is required when media model is enabled"
            )

        provider = providers.get(normalized_provider_id)
        if not isinstance(provider, dict):
            raise ProviderSettingsNotFound(
                f"Provider is not connected: {normalized_provider_id}"
            )
        media_config = get_provider_media_config(
            normalized_provider_id,
            provider,
            app_home=self.config_path.parent,
        )
        api_key = media_config["api_key"]
        if not api_key:
            raise ProviderSettingsNotFound(f"Provider is not connected: {normalized_provider_id}")

        return {
            "provider": media_config["provider"],
            "api_key": api_key,
            "model": normalized_model,
            "base_url": media_config["base_url"],
        }

    def list_media(self) -> dict[str, Any]:
        """Return media model settings without leaking API keys."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        provider_choices = [
            payload
            for provider_id, provider, preset_id, preset in connected_provider_entries(providers, presets)
            if (payload := self._provider_choice_payload(provider_id, provider, preset_id, preset))
        ]

        return {
            "sections": {
                category: self._section_payload(category, getattr(loaded, category) or section_type(), providers)
                for category, section_type in MEDIA_SECTIONS.items()
            },
            "providers": provider_choices,
            "restart_required": False,
            "media_file": str(Config.get_media_file_path(self.config_path, main_data)),
        }

    def update_media(self, category: str, *, enabled: bool, provider_id: str | None, model: str | None) -> dict[str, Any]:
        """Update one media model category."""
        if category not in MEDIA_SECTIONS:
            raise ProviderSettingsValidationError(f"Unknown media category: {category}")

        main_data, providers, _loaded = self._load_state()
        media_path = Config.ensure_media_file(self.config_path, main_data)
        media_data = load_json_dict(media_path)
        current = media_data.get(category, {}) if isinstance(media_data.get(category), dict) else {}
        next_section = dict(current)
        next_section["enabled"] = bool(enabled)

        if enabled:
            next_section.update(self._enabled_section_update(provider_id, model, providers))
        else:
            next_section.setdefault("provider", current.get("provider") or "minimax")
            next_section.setdefault("api_key", current.get("api_key") or "")
            next_section.setdefault("model", current.get("model") or "")
            next_section.setdefault("base_url", current.get("base_url"))

        media_data[category] = MEDIA_SECTIONS[category](**next_section).model_dump()
        Config.write_media_file(self.config_path, media_data, main_data)
        return {"ok": True, "category": category, "restart_required": True, "media": self.list_media()}
