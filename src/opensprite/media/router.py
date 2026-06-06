"""Routing helpers for media analysis providers."""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Protocol

from ..bus.message import UserMessage
from ..context.paths import get_session_workspace
from ..utils.log import logger
from .base import ImageAnalysisProvider, SpeechToTextProvider, VideoAnalysisProvider


class MediaRouter:
    """Route media analysis calls to configured providers."""

    IMAGE_PROVIDER_UNAVAILABLE = (
        "Error: image analysis is unavailable because no vision provider is configured."
    )
    OCR_PROVIDER_UNAVAILABLE = (
        "Error: OCR is unavailable because no OCR provider is configured."
    )
    SPEECH_PROVIDER_UNAVAILABLE = (
        "Error: audio transcription is unavailable because no speech provider is configured."
    )
    VIDEO_PROVIDER_UNAVAILABLE = (
        "Error: video analysis is unavailable because no video provider is configured."
    )
    EMPTY_IMAGE_RESULT = "Error: image analysis provider returned no usable result."
    EMPTY_OCR_RESULT = "Error: OCR provider returned no usable result."
    EMPTY_SPEECH_RESULT = "Error: speech provider returned no transcription text."
    EMPTY_VIDEO_RESULT = "Error: video analysis provider returned no usable result."

    def __init__(
        self,
        *,
        image_provider: ImageAnalysisProvider | None = None,
        ocr_provider: ImageAnalysisProvider | None = None,
        speech_provider: SpeechToTextProvider | None = None,
        video_provider: VideoAnalysisProvider | None = None,
    ):
        self.image_provider = image_provider
        self.ocr_provider = ocr_provider
        self.speech_provider = speech_provider
        self.video_provider = video_provider

    async def analyze_image(
        self,
        instruction: str,
        images: list[str],
        *,
        image_index: int = 0,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Analyze one image from the current turn."""
        if self.image_provider is None:
            return self.IMAGE_PROVIDER_UNAVAILABLE
        if not images:
            return "Error: no images are available in the current turn."
        if image_index < 0 or image_index >= len(images):
            return f"Error: image_index {image_index} is out of range for {len(images)} image(s)."
        result = await self.image_provider.analyze(
            instruction,
            [images[image_index]],
            model=model,
            max_tokens=max_tokens,
        )
        return result if result.strip() else self.EMPTY_IMAGE_RESULT

    async def ocr_image(
        self,
        instruction: str,
        images: list[str],
        *,
        image_index: int = 0,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Extract text from one image using the configured OCR provider."""
        if self.ocr_provider is None:
            return self.OCR_PROVIDER_UNAVAILABLE
        if not images:
            return "Error: no images are available in the current turn."
        if image_index < 0 or image_index >= len(images):
            return f"Error: image_index {image_index} is out of range for {len(images)} image(s)."
        result = await self.ocr_provider.analyze(
            instruction,
            [images[image_index]],
            model=model,
            max_tokens=max_tokens,
        )
        return result if result.strip() else self.EMPTY_OCR_RESULT

    async def transcribe_audio(
        self,
        audios: list[str],
        *,
        audio_index: int = 0,
        model: str | None = None,
        language: str | None = None,
    ) -> str:
        """Transcribe one audio clip from the current turn."""
        if self.speech_provider is None:
            return self.SPEECH_PROVIDER_UNAVAILABLE
        if not audios:
            return "Error: no audio is available in the current turn."
        if audio_index < 0 or audio_index >= len(audios):
            return f"Error: audio_index {audio_index} is out of range for {len(audios)} audio clip(s)."
        result = await self.speech_provider.transcribe(
            audios[audio_index],
            model=model,
            language=language,
        )
        return result if result.strip() else self.EMPTY_SPEECH_RESULT

    async def analyze_video(
        self,
        instruction: str,
        videos: list[str],
        *,
        video_index: int = 0,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Analyze one video clip from the current turn."""
        if self.video_provider is None:
            return self.VIDEO_PROVIDER_UNAVAILABLE
        if not videos:
            return "Error: no videos are available in the current turn."
        if video_index < 0 or video_index >= len(videos):
            return f"Error: video_index {video_index} is out of range for {len(videos)} video clip(s)."
        result = await self.video_provider.analyze(
            instruction,
            videos[video_index],
            model=model,
            max_tokens=max_tokens,
        )
        return result if result.strip() else self.EMPTY_VIDEO_RESULT

MEDIA_ARTIFACT_KINDS = frozenset({"image_text", "image_analysis", "audio_transcript", "video_analysis"})
MEDIA_ONLY_HISTORY_MARKER = "[Media-only message saved to workspace]"
INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON = "unsupported-payload"

OUTBOUND_MEDIA_KEYS = {
    "image": "images",
    "voice": "voices",
    "audio": "audios",
    "video": "videos",
}


class MediaArtifactLike(Protocol):
    kind: str
    ok: bool


class PreparedAudioTurnInput(Protocol):
    audio_files: list[str]


def is_media_artifact_kind(kind: str | None) -> bool:
    return str(kind or "").strip() in MEDIA_ARTIFACT_KINDS


def count_media_artifacts(artifacts: Iterable[MediaArtifactLike]) -> int:
    return sum(1 for artifact in artifacts if artifact.ok and is_media_artifact_kind(artifact.kind))


def media_artifact_gap_follow_up_instruction(media_gap: str) -> str:
    return (
        "\n- Quality follow-up: the previous pass did not produce typed artifacts for every required resource. "
        "Use the relevant media/source tools for each missing resource before finalizing. "
        "Do not claim completion until each required resource has a concrete tool-derived result.\n"
        f"{media_gap}"
    )


def outbound_media_error_result(
    message: str,
    *,
    category: str,
    invalid_arguments: bool = False,
) -> str:
    from ..tools.result_status import tool_error_result

    error = str(message or "").strip()
    return tool_error_result(
        error,
        error_type="SendMediaToolError",
        category=category,
        repeated_error_key=error if invalid_arguments else None,
        invalid_arguments=invalid_arguments,
        metadata={"tool_name": "send_media"},
    )


@dataclass(frozen=True)
class AudioInputPreprocessResult:
    """Outcome from optional audio-to-text preprocessing."""

    transcribed: bool = False
    status: str = "skipped"
    audio_files: tuple[str, ...] = ()
    transcript_len: int = 0


class AudioInputPreprocessor:
    """Convert dictated audio into text before the LLM sees the turn."""

    DICTATION_MODES = frozenset({"dictation", "voice"})
    UPLOAD_MODES = frozenset({"upload", "file"})

    def __init__(self, transcribe_audio: Callable[[list[str]], Awaitable[str]]):
        self._transcribe_audio = transcribe_audio

    @staticmethod
    def is_audio_only_message(user_message: UserMessage) -> bool:
        """Return whether a turn only carries audio and no written instruction."""
        return (
            bool(user_message.audios)
            and not bool(user_message.images or user_message.videos)
            and not (user_message.text or "").strip()
        )

    @classmethod
    def should_pretranscribe(cls, user_message: UserMessage) -> bool:
        """Return whether pure audio should be treated as dictated user text."""
        if not cls.is_audio_only_message(user_message):
            return False
        metadata = user_message.metadata if isinstance(user_message.metadata, dict) else {}
        mode = str(metadata.get("audio_input_mode") or "").strip().lower()
        if mode in cls.DICTATION_MODES:
            return True
        if mode in cls.UPLOAD_MODES:
            return False
        audio_kinds = metadata.get("audio_kinds")
        return isinstance(audio_kinds, list) and bool(audio_kinds) and all(kind == "voice" for kind in audio_kinds)

    async def preprocess(
        self,
        user_message: UserMessage,
        turn: PreparedAudioTurnInput,
    ) -> AudioInputPreprocessResult:
        """Turn pure dictated audio into text before task classification and LLM prompting."""
        if not self.should_pretranscribe(user_message):
            return AudioInputPreprocessResult()

        transcript = (await self._transcribe_audio(list(user_message.audios or []))).strip()
        metadata = user_message.metadata
        from ..tools.result_status import classify_tool_result_status

        if not classify_tool_result_status(transcript).ok:
            metadata["audio_transcription_error"] = transcript
            user_message.text = transcript
            status = "failed"
        else:
            metadata["audio_transcript"] = transcript
            user_message.text = self.format_transcript_message(transcript, turn.audio_files)
            status = "completed"
        user_message.audios = None
        return AudioInputPreprocessResult(
            transcribed=True,
            status=status,
            audio_files=tuple(turn.audio_files),
            transcript_len=len(transcript),
        )

    @staticmethod
    def format_transcript_message(transcript: str, audio_files: list[str]) -> str:
        """Combine dictated text with the saved source path for LLM context."""
        text = transcript.strip()
        if audio_files:
            text = f"{text}\n\n[Uploaded file path(s): {', '.join(audio_files)}]"
        return text

    @staticmethod
    def audio_files_for_llm(user_message: UserMessage, turn: PreparedAudioTurnInput) -> list[str] | None:
        """Hide already-transcribed audio attachments from media tool hints."""
        if "audio_transcript" in user_message.metadata or "audio_transcription_error" in user_message.metadata:
            return None
        return turn.audio_files


INBOUND_IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}

INBOUND_AUDIO_EXTENSIONS = {
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "audio/mp4": "m4a",
}

INBOUND_VIDEO_EXTENSIONS = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "video/x-matroska": "mkv",
}


@dataclass(frozen=True)
class InboundMediaPersistResult:
    files: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


class AgentMediaService:
    """Decode, persist, and format media attached to agent turns."""

    def __init__(
        self,
        *,
        workspace_root_getter: Callable[[], Path],
        app_home_getter: Callable[[], Path | None],
    ):
        self._workspace_root_getter = workspace_root_getter
        self._app_home_getter = app_home_getter

    @staticmethod
    def decode_data_url(payload: str, media_prefix: str) -> tuple[str, bytes] | None:
        """Decode a media data URL into a MIME type and bytes."""
        value = str(payload or "").strip()
        if not value.startswith("data:"):
            return None

        header, separator, encoded = value.partition(",")
        if not separator or ";base64" not in header.lower():
            return None

        mime_type = header[5:].split(";", 1)[0].strip().lower()
        if not mime_type.startswith(f"{media_prefix}/"):
            return None

        try:
            return mime_type, base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            return None

    def persist_inbound_media(
        self,
        session_id: str,
        media_items: list[str] | None,
        *,
        media_prefix: str,
        directory_name: str,
        extensions: dict[str, str],
    ) -> list[str]:
        """Persist inbound media data URLs under a session workspace directory."""
        return self.persist_inbound_media_with_events(
            session_id,
            media_items,
            media_prefix=media_prefix,
            directory_name=directory_name,
            extensions=extensions,
        ).files

    def persist_inbound_media_with_events(
        self,
        session_id: str,
        media_items: list[str] | None,
        *,
        media_prefix: str,
        directory_name: str,
        extensions: dict[str, str],
    ) -> InboundMediaPersistResult:
        """Persist inbound media and return traceable lifecycle events."""
        if not media_items:
            return InboundMediaPersistResult()

        workspace = get_session_workspace(
            session_id,
            workspace_root=self._workspace_root_getter(),
            app_home=self._app_home_getter(),
        )
        media_dir = workspace / directory_name
        saved_files: list[str] = []
        events: list[dict[str, Any]] = []

        for index, item in enumerate(media_items, start=1):
            decoded = self.decode_data_url(item, media_prefix)
            if decoded is None:
                events.append(
                    {
                        "media_type": media_prefix,
                        "status": "skipped",
                        "index": index,
                        "reason": INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON,
                    }
                )
                logger.warning(
                    "[{}] inbound.{}.persist.skip | index={} reason={}",
                    session_id,
                    media_prefix,
                    index,
                    INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON,
                )
                continue

            mime_type, media_bytes = decoded
            extension = extensions.get(mime_type, "bin")
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"inbound-{timestamp}-{time.time_ns()}-{index}.{extension}"
                target = media_dir / filename
                target.write_bytes(media_bytes)
                relative_path = target.relative_to(workspace).as_posix()
                saved_files.append(relative_path)
                events.append(
                    {
                        "media_type": media_prefix,
                        "status": "persisted",
                        "index": index,
                        "mime_type": mime_type,
                        "file": relative_path,
                        "bytes": len(media_bytes),
                    }
                )
                logger.info(
                    "[{}] inbound.{}.persisted | file={}",
                    session_id,
                    media_prefix,
                    target,
                )
            except Exception as exc:
                events.append({"media_type": media_prefix, "status": "failed", "index": index, "mime_type": mime_type, "error": str(exc)})
                logger.warning(
                    "[{}] inbound.{}.persist.failed | index={} error={}",
                    session_id,
                    media_prefix,
                    index,
                    exc,
                )

        return InboundMediaPersistResult(files=saved_files, events=events)

    def persist_inbound_images(self, session_id: str, images: list[str] | None) -> list[str]:
        """Persist inbound image data URLs under the session workspace images directory."""
        return self.persist_inbound_media(
            session_id,
            images,
            media_prefix="image",
            directory_name="images",
            extensions=INBOUND_IMAGE_EXTENSIONS,
        )

    def persist_inbound_audios(self, session_id: str, audios: list[str] | None) -> list[str]:
        """Persist inbound audio data URLs under the session workspace audios directory."""
        return self.persist_inbound_media(
            session_id,
            audios,
            media_prefix="audio",
            directory_name="audios",
            extensions=INBOUND_AUDIO_EXTENSIONS,
        )

    def persist_inbound_videos(self, session_id: str, videos: list[str] | None) -> list[str]:
        """Persist inbound video data URLs under the session workspace videos directory."""
        return self.persist_inbound_media(
            session_id,
            videos,
            media_prefix="video",
            directory_name="videos",
            extensions=INBOUND_VIDEO_EXTENSIONS,
        )

    @staticmethod
    def is_media_only_message(
        *,
        text: str | None,
        images: list[str] | None,
        audios: list[str] | None,
        videos: list[str] | None,
    ) -> bool:
        """Return whether a turn only carries media without user instructions."""
        has_media = bool(images or audios or videos)
        return has_media and not (text or "").strip()

    @staticmethod
    def format_saved_media_history_content(
        *,
        image_files: list[str],
        audio_files: list[str],
        video_files: list[str],
    ) -> str:
        """Format saved media paths as readable user-message history content."""
        lines = [MEDIA_ONLY_HISTORY_MARKER]
        if image_files:
            lines.append("Images: " + ", ".join(image_files))
        if audio_files:
            lines.append("Audios: " + ", ".join(audio_files))
        if video_files:
            lines.append("Videos: " + ", ".join(video_files))
        return "\n".join(lines)

    @staticmethod
    def queue_outbound_media(
        media: dict[str, list[str]] | None,
        kind: str,
        payload: str,
    ) -> str | None:
        """Queue one media payload into the active turn's outbound media bucket."""
        if media is None:
            return outbound_media_error_result(
                "outbound media can only be queued while processing a user message.",
                category="missing_turn_context",
            )

        key = OUTBOUND_MEDIA_KEYS.get(kind)
        if key is None:
            return outbound_media_error_result(
                f"unsupported outbound media kind: {kind}",
                category="invalid_arguments",
                invalid_arguments=True,
            )

        value = str(payload or "").strip()
        if not value:
            return outbound_media_error_result(
                "outbound media payload cannot be empty.",
                category="invalid_arguments",
                invalid_arguments=True,
            )

        media.setdefault(key, []).append(value)
        return None

    @staticmethod
    def queued_outbound_media(media: dict[str, list[str]] | None) -> dict[str, list[str]]:
        """Return a stable outbound media shape for one assistant reply."""
        media = media or {}
        return {key: list(media.get(key) or []) for key in ("images", "voices", "audios", "videos")}

    @staticmethod
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
        hints: list[str] = []
        if user_images:
            hints.append(
                f"User attached {len(user_images)} image(s). Use analyze_image or ocr_image only if "
                "the user's text asks for visual understanding or text extraction."
            )
            if user_image_files:
                hints.append(
                    f"Saved inbound image file(s) under the session workspace: {', '.join(user_image_files)}."
                )
        if user_audios:
            hints.append(
                f"User attached {len(user_audios)} audio clip(s). Use transcribe_audio only if "
                "the user's text asks for spoken content."
            )
            if user_audio_files:
                hints.append(
                    f"Saved inbound audio file(s) under the session workspace: {', '.join(user_audio_files)}."
                )
        if user_videos:
            hints.append(
                f"User attached {len(user_videos)} video clip(s). Use analyze_video only if "
                "the user's text asks for video understanding."
            )
            if user_video_files:
                hints.append(
                    f"Saved inbound video file(s) under the session workspace: {', '.join(user_video_files)}."
                )
        if not hints:
            return current_message
        return f"{current_message}\n\n[{ ' '.join(hints) }]"
