"""Pure normalization policy for session identities and path-safe segments."""

from __future__ import annotations

import hashlib
import re


def split_session_id(session_id: str | None) -> tuple[str, str]:
    """Split a session id into channel and raw external chat id."""
    value = (session_id or "default").strip() or "default"
    if ":" in value:
        channel, external_chat_id = value.split(":", 1)
        return channel.strip() or "default", external_chat_id.strip() or "default"
    return "default", value


def sanitize_path_segment(
    value: str,
    default: str = "default",
    max_length: int = 48,
) -> str:
    """Sanitize a path segment while keeping collisions unlikely."""
    raw = (value or "").strip() or default
    normalized = re.sub(r"\s+", "-", raw)
    slug = re.sub(r"[^A-Za-z0-9._-]", "-", normalized)
    slug = re.sub(r"-+", "-", slug).strip(" ._-") or default

    needs_hash = slug != raw or len(slug) > max_length
    slug = slug[:max_length].rstrip(" ._-") or default
    if needs_hash:
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug}-{digest}"[: max_length + 9].rstrip(" ._-")
    return slug or default
