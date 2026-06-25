"""Shared media model settings helpers for Web settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth.credentials import CredentialNotFoundError, resolve_credential
from .json_files import load_json_dict
from .llm_presets import load_llm_presets
from .provider_choices import (
    get_model_choices,
    get_provider_choices,
    get_provider_preset_id,
)
from .provider_errors import (
    ProviderSettingsNotFound,
    ProviderSettingsValidationError,
)
from .provider_discovery import fetch_openrouter_image_models
from .schema import Config, OcrConfig, SpeechConfig, VideoConfig, VisionConfig


MEDIA_SECTIONS = {
    "vision": VisionConfig,
    "ocr": OcrConfig,
    "speech": SpeechConfig,
    "video": VideoConfig,
}


def _dedupe_media_models(models: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for model in models:
        normalized = str(model or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def discover_media_model_choices(preset_id: str | None, preset: Any) -> tuple[dict[str, list[str]], str]:
    fallback = {
        category: list(models)
        for category, models in (preset.media_model_choices or {}).items()
    } if preset else {}
    discovery = getattr(preset, "media_discovery", None) if preset else None
    discovery_type = str(discovery.get("type") or "").strip() if isinstance(discovery, dict) else ""
    if discovery_type != "openrouter_image":
        return fallback, "preset"

    live_image_models = fetch_openrouter_image_models()
    if not live_image_models:
        return fallback, "preset"

    vision = _dedupe_media_models(live_image_models + fallback.get("vision", []))
    ocr = _dedupe_media_models(fallback.get("ocr", []) + live_image_models)
    media_models = dict(fallback)
    media_models["vision"] = vision
    media_models["ocr"] = ocr
    return media_models, "live"


class MediaSettingsService:
    """Read and mutate media model settings on disk."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).expanduser().resolve()

    def _load_main_data(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise ProviderSettingsNotFound(f"Config file not found: {self.config_path}")
        return load_json_dict(self.config_path)

    def _load_state(self) -> tuple[dict[str, Any], dict[str, Any], Config]:
        main_data = self._load_main_data()
        loaded = Config.from_json(self.config_path)
        providers = {name: provider.model_dump() for name, provider in loaded.llm.providers.items()}
        return main_data, providers, loaded

    @staticmethod
    def _provider_api_key(provider_id: str, provider: dict[str, Any], *, app_home: Path) -> str:
        api_key = str(provider.get("api_key", "") or "").strip()
        if api_key:
            return api_key
        credential_id = str(provider.get("credential_id", "") or "").strip()
        if not credential_id:
            return ""
        try:
            return resolve_credential(
                provider=str(provider.get("provider") or provider_id).strip() or provider_id,
                credential_id=credential_id,
                app_home=app_home,
            ).secret
        except CredentialNotFoundError:
            return ""

    def _section_payload(self, category: str, config: Any, providers: dict[str, Any]) -> dict[str, Any]:
        provider_id = self._section_provider_id(config, providers)
        return {
            "category": category,
            "enabled": bool(config.enabled),
            "provider": config.provider,
            "provider_id": provider_id,
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
            provider_name = provider.get("provider") or candidate_id
            if (
                self._provider_api_key(
                    candidate_id,
                    provider,
                    app_home=self.config_path.parent,
                ) == expected_api_key
                and str(self._media_base_url(candidate_id, provider) or "") == expected_base_url
                and provider_name == config.provider
            ):
                return candidate_id
        return ""

    @staticmethod
    def _media_base_url(provider_id: str, provider: dict[str, Any]) -> str | None:
        base_url = provider.get("base_url")
        if str(provider.get("provider") or provider_id).strip() == "minimax":
            return "https://api.minimax.io/v1"
        return base_url

    def _provider_choice_payload(
        self,
        provider_id: str,
        provider: dict[str, Any],
        presets: Any,
    ) -> dict[str, Any] | None:
        if not self._provider_api_key(provider_id, provider, app_home=self.config_path.parent):
            return None
        preset_id = get_provider_preset_id(provider_id, provider, presets)
        preset = presets.providers.get(preset_id) if preset_id else None
        choices, selected = get_model_choices(
            str(provider.get("model") or "") or None,
            model_choices=preset.model_choices if preset else (),
        )
        media_models, media_model_source = discover_media_model_choices(preset_id, preset)
        return {
            "id": provider_id,
            "provider": preset_id or provider_id,
            "name": str(provider.get("name") or "").strip() or (preset.display_name if preset else provider_id),
            "model": selected or "",
            "models": choices,
            "media_models": media_models,
            "media_model_source": media_model_source,
        }

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
        api_key = self._provider_api_key(
            normalized_provider_id,
            provider,
            app_home=self.config_path.parent,
        )
        if not api_key:
            raise ProviderSettingsNotFound(f"Provider is not connected: {normalized_provider_id}")

        preset_id = str(provider.get("provider") or normalized_provider_id).strip()
        return {
            "provider": preset_id,
            "api_key": api_key,
            "model": normalized_model,
            "base_url": self._media_base_url(normalized_provider_id, provider),
        }

    def list_media(self) -> dict[str, Any]:
        """Return media model settings without leaking API keys."""
        main_data, providers, loaded = self._load_state()
        presets = load_llm_presets()
        provider_choices = []
        for provider_id in get_provider_choices({"llm": {"providers": providers}}, provider_order=presets.provider_order):
            provider = providers.get(provider_id, {})
            if not isinstance(provider, dict):
                continue
            payload = self._provider_choice_payload(provider_id, provider, presets)
            if payload:
                provider_choices.append(payload)

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
