import pytest

from opensprite.modules.media.inbound import (
    INBOUND_AUDIO_EXTENSIONS,
    INBOUND_IMAGE_EXTENSIONS,
    INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON,
    INBOUND_VIDEO_EXTENSIONS,
    decode_data_url,
)


def test_inbound_media_reason_markers_are_stable():
    assert INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON == "unsupported-payload"


def test_inbound_media_extension_maps_are_stable():
    assert INBOUND_IMAGE_EXTENSIONS == {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    assert INBOUND_AUDIO_EXTENSIONS == {
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/mp4": "m4a",
    }
    assert INBOUND_VIDEO_EXTENSIONS == {
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/quicktime": "mov",
        "video/x-matroska": "mkv",
    }


def test_decode_data_url_normalizes_mime_type_and_decodes_strict_base64():
    assert decode_data_url(" data:IMAGE/PNG;base64,aGVsbG8= ", "image") == (
        "image/png",
        b"hello",
    )


@pytest.mark.parametrize(
    "payload,media_prefix",
    [
        ("https://example.com/image.png", "image"),
        ("data:image/png;base64", "image"),
        ("data:image/png,raw", "image"),
        ("data:image/png;base64,aGVsbG8=", "audio"),
        ("data:image/png;base64,not-valid-base64", "image"),
    ],
)
def test_decode_data_url_rejects_unsupported_payloads(payload, media_prefix):
    assert decode_data_url(payload, media_prefix) is None
