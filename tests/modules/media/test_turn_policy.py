from opensprite.modules.media.turn_policy import (
    MEDIA_ONLY_HISTORY_FAILURE_MARKER,
    MEDIA_ONLY_HISTORY_MARKER,
    MEDIA_ONLY_HISTORY_PARTIAL_FAILURE_MARKER,
    augment_message_for_media,
    format_failed_media_history_content,
    format_partially_saved_media_history_content,
    format_saved_media_history_content,
    is_media_only_message,
)


def test_media_only_policy_requires_media_without_written_text():
    assert is_media_only_message(text="  ", images=["image"], audios=None, videos=None)
    assert is_media_only_message(text=None, images=None, audios=["audio"], videos=None)
    assert is_media_only_message(text="", images=None, audios=None, videos=["video"])
    assert not is_media_only_message(text="inspect", images=["image"], audios=None, videos=None)
    assert not is_media_only_message(text="", images=None, audios=None, videos=None)


def test_media_history_formatters_preserve_stable_content():
    assert format_saved_media_history_content(
        image_files=["images/a.png"],
        audio_files=["audios/a.wav"],
        video_files=["videos/a.mp4"],
    ) == (
        f"{MEDIA_ONLY_HISTORY_MARKER}\n"
        "Images: images/a.png\n"
        "Audios: audios/a.wav\n"
        "Videos: videos/a.mp4"
    )
    assert format_failed_media_history_content() == MEDIA_ONLY_HISTORY_FAILURE_MARKER
    assert format_partially_saved_media_history_content(
        image_files=["images/a.png"],
        audio_files=[],
        video_files=[],
        failed_count=-1,
    ) == (
        f"{MEDIA_ONLY_HISTORY_MARKER}\n"
        "Images: images/a.png\n"
        f"{MEDIA_ONLY_HISTORY_PARTIAL_FAILURE_MARKER}\n"
        "Unsaved attachments: 0"
    )


def test_augment_message_for_media_returns_original_message_without_media():
    message = "".join(["No", " media"])

    result = augment_message_for_media(message, None, None, None)

    assert result is message


def test_augment_message_for_media_preserves_all_hints_and_saved_paths():
    result = augment_message_for_media(
        "Inspect attachments",
        ["image-a", "image-b"],
        ["audio-a"],
        ["video-a"],
        user_image_files=["images/a.png", "images/b.png"],
        user_audio_files=["audios/a.wav"],
        user_video_files=["videos/a.mp4"],
    )

    assert result.startswith("Inspect attachments\n\n[")
    assert "User attached 2 image(s)." in result
    assert "Saved inbound image file(s) under the session workspace: images/a.png, images/b.png." in result
    assert "User attached 1 audio clip(s)." in result
    assert "Saved inbound audio file(s) under the session workspace: audios/a.wav." in result
    assert "User attached 1 video clip(s)." in result
    assert "Saved inbound video file(s) under the session workspace: videos/a.mp4." in result
    assert result.endswith("]")
