"""Per-turn context and input preparation helpers for AgentLoop."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from ..bus.message import UserMessage
from ..utils.log import logger
from .media import (
    AgentMediaService,
    INBOUND_AUDIO_EXTENSIONS,
    INBOUND_IMAGE_EXTENSIONS,
    INBOUND_VIDEO_EXTENSIONS,
)


class TurnContextService:
    """Activates task-local context for one user message turn."""

    def __init__(
        self,
        *,
        current_session_id: ContextVar[str | None],
        current_channel: ContextVar[str | None],
        current_external_chat_id: ContextVar[str | None],
        current_images: ContextVar[list[str] | None],
        current_audios: ContextVar[list[str] | None],
        current_videos: ContextVar[list[str] | None],
        current_outbound_media: ContextVar[dict[str, list[str]] | None],
        current_run_id: ContextVar[str | None],
        current_work_progress: ContextVar[dict[str, Any] | None],
    ):
        self._current_session_id = current_session_id
        self._current_channel = current_channel
        self._current_external_chat_id = current_external_chat_id
        self._current_images = current_images
        self._current_audios = current_audios
        self._current_videos = current_videos
        self._current_outbound_media = current_outbound_media
        self._current_run_id = current_run_id
        self._current_work_progress = current_work_progress

    def current_session_id(self) -> str | None:
        """Return the current task-local session id."""
        return self._current_session_id.get()

    def current_channel(self) -> str | None:
        """Return the current task-local channel."""
        return self._current_channel.get()

    def current_external_chat_id(self) -> str | None:
        """Return the current transport-level chat id."""
        return self._current_external_chat_id.get()

    def current_images(self) -> list[str] | None:
        """Return images attached to the current active turn."""
        return self._current_images.get()

    def current_audios(self) -> list[str] | None:
        """Return audios attached to the current active turn."""
        return self._current_audios.get()

    def current_videos(self) -> list[str] | None:
        """Return videos attached to the current active turn."""
        return self._current_videos.get()

    def current_run_id(self) -> str | None:
        """Return the current task-local run id."""
        return self._current_run_id.get()

    def queue_outbound_media(self, kind: str, payload: str) -> str | None:
        """Queue one media payload to be attached to the current assistant reply."""
        return AgentMediaService.queue_outbound_media(self._current_outbound_media.get(), kind, payload)

    def queued_outbound_media(self) -> dict[str, list[str]]:
        """Return queued outbound media for the current turn."""
        return AgentMediaService.queued_outbound_media(self._current_outbound_media.get())

    def reset_work_progress(self) -> None:
        """Reset per-pass progress signals while keeping turn context active."""
        self._current_work_progress.set(self._default_work_progress())

    def note_file_change(self, path: str) -> None:
        """Record one file-change signal for the active pass."""
        state = self._current_work_progress.get()
        if state is None:
            return
        normalized_path = str(path or "").strip()
        state["file_change_count"] = int(state.get("file_change_count", 0)) + 1
        if normalized_path and normalized_path not in state["touched_paths"]:
            state["touched_paths"].append(normalized_path)

    def snapshot_work_progress(self) -> dict[str, Any]:
        """Return the current per-pass progress signals."""
        state = self._current_work_progress.get() or self._default_work_progress()
        return {
            "file_change_count": int(state.get("file_change_count", 0)),
            "touched_paths": tuple(str(path) for path in state.get("touched_paths", []) if str(path).strip()),
        }

    @staticmethod
    def _default_work_progress() -> dict[str, Any]:
        return {"file_change_count": 0, "touched_paths": []}

    @contextmanager
    def activate(
        self,
        *,
        session_id: str,
        channel: str | None,
        external_chat_id: str | None,
        images: list[str] | None,
        audios: list[str] | None,
        videos: list[str] | None,
        run_id: str,
    ) -> Iterator[None]:
        """Set per-turn context values and reset them in reverse order."""
        token = self._current_session_id.set(session_id)
        channel_token = self._current_channel.set(channel)
        external_chat_id_token = self._current_external_chat_id.set(external_chat_id)
        images_token = self._current_images.set(list(images or []))
        audios_token = self._current_audios.set(list(audios or []))
        videos_token = self._current_videos.set(list(videos or []))
        outbound_media_token = self._current_outbound_media.set(
            {"images": [], "voices": [], "audios": [], "videos": []}
        )
        run_token = self._current_run_id.set(run_id)
        work_progress_token = self._current_work_progress.set(self._default_work_progress())
        try:
            yield
        finally:
            self._current_work_progress.reset(work_progress_token)
            self._current_run_id.reset(run_token)
            self._current_outbound_media.reset(outbound_media_token)
            self._current_videos.reset(videos_token)
            self._current_audios.reset(audios_token)
            self._current_images.reset(images_token)
            self._current_external_chat_id.reset(external_chat_id_token)
            self._current_channel.reset(channel_token)
            self._current_session_id.reset(token)


QUICK_ACTION_METADATA_KEY = "quick_action"
TURN_SOURCE_METADATA_KEY = "source"
CLI_VIA_WEB_TURN_SOURCE = "cli_via_web"
RESUME_FOLLOW_UP_QUICK_ACTION = "resume_follow_up"
RUN_VERIFICATION_QUICK_ACTION = "run_verification"


def metadata_is_cli_via_web(metadata: dict[str, Any]) -> bool:
    return str(metadata.get(TURN_SOURCE_METADATA_KEY) or "").strip() == CLI_VIA_WEB_TURN_SOURCE


def metadata_requests_follow_up_resume(metadata: dict[str, Any]) -> bool:
    return _quick_action(metadata) == RESUME_FOLLOW_UP_QUICK_ACTION


def metadata_requests_direct_verification(metadata: dict[str, Any]) -> bool:
    return _quick_action(metadata) == RUN_VERIFICATION_QUICK_ACTION


def _quick_action(metadata: dict[str, Any]) -> str:
    return str(metadata.get(QUICK_ACTION_METADATA_KEY) or "").strip()


@dataclass(frozen=True)
class PreparedTurnInput:
    """Resolved user turn data used by process orchestration."""

    session_id: str
    channel: str | None
    external_chat_id: str | None
    image_files: list[str]
    audio_files: list[str]
    video_files: list[str]
    media_events: list[dict[str, Any]]
    user_metadata: dict[str, Any]
    assistant_metadata: dict[str, Any]


class TurnInputPreparer:
    """Resolves turn ids, persists inbound media, and builds message metadata."""

    def __init__(
        self,
        *,
        media_service: AgentMediaService,
        format_log_preview: Callable[..., str],
    ):
        self.media_service = media_service
        self._format_log_preview = format_log_preview

    def prepare(self, user_message: UserMessage) -> PreparedTurnInput:
        """Prepare all process input fields derived directly from the inbound message."""
        session_id = user_message.session_id or user_message.external_chat_id or "default"
        channel = user_message.channel or None

        if ":" not in session_id:
            logger.warning(
                "Received non-namespaced session_id '{}' in Agent.process; this may mix sessions if MessageQueue is bypassed",
                session_id,
            )

        sender = user_message.sender_name or user_message.sender_id or "-"
        logger.info(
            f"[{session_id}] inbound | channel={channel or '-'} sender={sender} images={len(user_message.images or [])} "
            f"text={self._format_log_preview(user_message.text, max_chars=200)}"
        )
        image_result = self.media_service.persist_inbound_media_with_events(
            session_id,
            user_message.images,
            media_prefix="image",
            directory_name="images",
            extensions=INBOUND_IMAGE_EXTENSIONS,
        )
        audio_result = self.media_service.persist_inbound_media_with_events(
            session_id,
            user_message.audios,
            media_prefix="audio",
            directory_name="audios",
            extensions=INBOUND_AUDIO_EXTENSIONS,
        )
        video_result = self.media_service.persist_inbound_media_with_events(
            session_id,
            user_message.videos,
            media_prefix="video",
            directory_name="videos",
            extensions=INBOUND_VIDEO_EXTENSIONS,
        )
        image_files = image_result.files
        audio_files = audio_result.files
        video_files = video_result.files
        media_events = [*image_result.events, *audio_result.events, *video_result.events]

        user_metadata = {
            **dict(user_message.metadata or {}),
            "channel": channel,
            "external_chat_id": user_message.external_chat_id,
            "sender_id": user_message.sender_id,
            "sender_name": user_message.sender_name,
            "images_count": len(user_message.images or []),
            "image_files": image_files or None,
            "images_dir": "images" if image_files else None,
            "audios_count": len(user_message.audios or []),
            "audio_files": audio_files or None,
            "audios_dir": "audios" if audio_files else None,
            "videos_count": len(user_message.videos or []),
            "video_files": video_files or None,
            "videos_dir": "videos" if video_files else None,
        }
        user_metadata = {key: value for key, value in user_metadata.items() if value is not None}
        assistant_metadata = {
            "channel": channel,
            "external_chat_id": user_message.external_chat_id,
        }
        assistant_metadata = {key: value for key, value in assistant_metadata.items() if value is not None}
        external_chat_id = str(user_message.external_chat_id) if user_message.external_chat_id is not None else None

        return PreparedTurnInput(
            session_id=session_id,
            channel=channel,
            external_chat_id=external_chat_id,
            image_files=image_files,
            audio_files=audio_files,
            video_files=video_files,
            media_events=media_events,
            user_metadata=user_metadata,
            assistant_metadata=assistant_metadata,
        )
