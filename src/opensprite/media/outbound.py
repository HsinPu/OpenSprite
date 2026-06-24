"""Outbound media queue helpers."""

from __future__ import annotations


OUTBOUND_MEDIA_KEYS = {
    "image": "images",
    "voice": "voices",
    "audio": "audios",
    "video": "videos",
}


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


def queued_outbound_media(media: dict[str, list[str]] | None) -> dict[str, list[str]]:
    """Return a stable outbound media shape for one assistant reply."""
    media = media or {}
    return {key: list(media.get(key) or []) for key in ("images", "voices", "audios", "videos")}
