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

    image_provider = None
    if vision and vision.enabled:
        image_provider = create_image_analysis_provider(
            provider=vision.provider,
            api_key=vision.api_key,
            default_model=vision.model,
            base_url=vision.base_url,
        )

    ocr_provider = None
    if ocr and ocr.enabled:
        ocr_provider = create_image_analysis_provider(
            provider=ocr.provider,
            api_key=ocr.api_key,
            default_model=ocr.model,
            base_url=ocr.base_url,
        )

    speech_provider = None
    if speech and speech.enabled:
        speech_provider = OpenAICompatibleSpeechProvider(
            api_key=speech.api_key,
            default_model=speech.model,
            base_url=speech.base_url,
        )

    video_provider = None
    if video and video.enabled:
        video_provider = OpenAICompatibleVideoProvider(
            api_key=video.api_key,
            default_model=video.model,
            base_url=video.base_url,
        )

    return MediaRouter(
        image_provider=image_provider,
        ocr_provider=ocr_provider,
        speech_provider=speech_provider,
        video_provider=video_provider,
    )


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
