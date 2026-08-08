"""Provider-neutral policy for inbound media payloads."""

from __future__ import annotations

import base64
import binascii


INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON = "unsupported-payload"

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
