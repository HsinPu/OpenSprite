"""Audio transcription tool for OpenSprite."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..media import MediaRouter
from .base import Tool
from .saved_media import resolve_media_items


SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/mp4",
}


def _resolve_audios(
    *,
    current_audios: list[str] | None,
    workspace_resolver: Callable[[], Path] | None,
    audio_path: str = "",
) -> tuple[list[str], str | None]:
    """Resolve audio from either current turn attachments or a saved workspace path."""
    return resolve_media_items(
        current_items=current_audios,
        workspace_resolver=workspace_resolver,
        media_path=audio_path,
        media_label="audio",
        supported_mime_types=SUPPORTED_AUDIO_MIME_TYPES,
    )


class TranscribeAudioTool(Tool):
    """Tool to transcribe audio clips attached to the current user turn."""

    def __init__(
        self,
        media_router: MediaRouter,
        *,
        get_current_audios: Callable[[], list[str] | None],
        workspace_resolver: Callable[[], Path] | None = None,
    ):
        self._media_router = media_router
        self._get_current_audios = get_current_audios
        self._workspace_resolver = workspace_resolver

    @property
    def name(self) -> str:
        return "transcribe_audio"

    @property
    def description(self) -> str:
        return (
            "Transcribe one audio clip from the current user turn or a saved audio file in the session workspace into text. "
            "Use this for voice messages, spoken notes, recorded content, or earlier saved audio when you need the words."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "audio_index": {
                    "type": "integer",
                    "description": "Optional. Zero-based index into the current turn's attached audio clips. Defaults to 0.",
                    "default": 0,
                    "minimum": 0,
                },
                "language": {
                    "type": "string",
                    "description": "Optional language hint for transcription, such as en or zh.",
                },
                "audio_path": {
                    "type": "string",
                    "description": "Optional. Relative path to a saved audio file in the current session workspace, such as audios/inbound-....ogg. Use this to transcribe audio saved in an earlier turn.",
                },
            },
        }

    async def _execute(self, audio_index: int = 0, language: str | None = None, audio_path: str = "", **kwargs: Any) -> str:
        audios, error = _resolve_audios(
            current_audios=self._get_current_audios(),
            workspace_resolver=self._workspace_resolver,
            audio_path=audio_path,
        )
        if error:
            return error
        effective_index = 0 if audio_path.strip() else audio_index
        return await self._media_router.transcribe_audio(
            audios,
            audio_index=effective_index,
            language=language,
        )
