"""Provider-neutral policy for media-bearing user turns."""

from __future__ import annotations


MEDIA_ONLY_HISTORY_MARKER = "[Media-only message saved to workspace]"
MEDIA_ONLY_HISTORY_FAILURE_MARKER = "[Media-only message could not be saved]"
MEDIA_ONLY_HISTORY_PARTIAL_FAILURE_MARKER = "[Some media attachments could not be saved]"


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


def format_failed_media_history_content() -> str:
    """Format a media-only history entry when no attachment was persisted."""
    return MEDIA_ONLY_HISTORY_FAILURE_MARKER


def format_partially_saved_media_history_content(
    *,
    image_files: list[str],
    audio_files: list[str],
    video_files: list[str],
    failed_count: int,
) -> str:
    """Format saved paths and the number of attachments that were lost."""
    saved = format_saved_media_history_content(
        image_files=image_files,
        audio_files=audio_files,
        video_files=video_files,
    )
    return (
        f"{saved}\n{MEDIA_ONLY_HISTORY_PARTIAL_FAILURE_MARKER}\n"
        f"Unsaved attachments: {max(0, int(failed_count))}"
    )


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
