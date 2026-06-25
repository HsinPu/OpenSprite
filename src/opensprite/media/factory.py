"""Media router factory."""

from __future__ import annotations

from ..config import Config
from .audio import OpenAICompatibleSpeechProvider
from .image import create_image_analysis_provider
from .router import MediaRouter
from .video import OpenAICompatibleVideoProvider


def create_media_router(config: Config) -> MediaRouter:
    """Create the media router with optional analysis providers."""

    vision = getattr(config, "vision", None)
    ocr = getattr(config, "ocr", None)
    speech = getattr(config, "speech", None)
    video = getattr(config, "video", None)

    image_provider = _image_provider_from_config(vision)
    ocr_provider = _image_provider_from_config(ocr)

    speech_provider = _openai_compatible_provider_from_config(speech, OpenAICompatibleSpeechProvider)
    video_provider = _openai_compatible_provider_from_config(video, OpenAICompatibleVideoProvider)

    return MediaRouter(
        image_provider=image_provider,
        ocr_provider=ocr_provider,
        speech_provider=speech_provider,
        video_provider=video_provider,
    )


def _image_provider_from_config(config: object | None):
    kwargs = _provider_kwargs_from_config(config, include_provider=True)
    return create_image_analysis_provider(**kwargs) if kwargs is not None else None


def _openai_compatible_provider_from_config(config: object | None, provider_class):
    kwargs = _provider_kwargs_from_config(config)
    return provider_class(**kwargs) if kwargs is not None else None


def _provider_kwargs_from_config(config: object | None, *, include_provider: bool = False):
    if config is None or not getattr(config, "enabled", False):
        return None
    return {
        **({"provider": getattr(config, "provider")} if include_provider else {}),
        "api_key": getattr(config, "api_key"),
        "default_model": getattr(config, "model"),
        "base_url": getattr(config, "base_url"),
    }


def reload_media_router(current: MediaRouter | None, config: Config) -> MediaRouter:
    """Create or refresh a media router from the current config."""
    media_router = create_media_router(config)
    if current is None:
        return media_router
    current.replace_providers(media_router)
    return current


def media_router_status(router: MediaRouter) -> dict[str, bool]:
    """Return the provider availability payload for settings reload responses."""
    return {
        "vision_enabled": bool(router.image_provider),
        "ocr_enabled": bool(router.ocr_provider),
        "speech_enabled": bool(router.speech_provider),
        "video_enabled": bool(router.video_provider),
    }
