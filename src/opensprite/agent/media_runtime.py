"""Agent media runtime helpers."""

from __future__ import annotations

from typing import Any

from ..media import AgentMediaService, MediaRouter


def get_current_images(agent: Any) -> list[str] | None:
    """Return images attached to the current active turn."""
    return agent.turn_context.current_images()


def get_current_audios(agent: Any) -> list[str] | None:
    """Return audios attached to the current active turn."""
    return agent.turn_context.current_audios()


def get_current_videos(agent: Any) -> list[str] | None:
    """Return videos attached to the current active turn."""
    return agent.turn_context.current_videos()


async def transcribe_audio_input(agent: Any, audios: list[str]) -> str:
    """Transcribe inbound audio before treating it as user text."""
    router = agent.media_router or MediaRouter()
    return await router.transcribe_audio(audios)


def queue_outbound_media(agent: Any, kind: str, payload: str) -> str | None:
    """Queue one media payload to be attached to the current assistant reply."""
    return agent.turn_context.queue_outbound_media(kind, payload)


def get_queued_outbound_media(agent: Any) -> dict[str, list[str]]:
    """Return queued outbound media for the current turn."""
    return agent.turn_context.queued_outbound_media()


def augment_message_for_media(
    current_message: str,
    user_images: list[str] | None,
    user_audios: list[str] | None,
    user_videos: list[str] | None,
    user_image_files: list[str] | None = None,
    user_audio_files: list[str] | None = None,
    user_video_files: list[str] | None = None,
) -> str:
    """Add lightweight prompt hints when the current turn includes media."""
    return AgentMediaService.augment_message_for_media(
        current_message,
        user_images,
        user_audios,
        user_videos,
        user_image_files=user_image_files,
        user_audio_files=user_audio_files,
        user_video_files=user_video_files,
    )
