"""Shared helpers for resolving saved session media files."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Callable


def load_saved_media_data_url(
    workspace: Path,
    media_path: str,
    *,
    supported_mime_types: set[str] | frozenset[str],
) -> str | None:
    """Load a saved session-workspace media file as a base64 data URL."""
    relative_path = str(media_path or "").strip().replace("\\", "/")
    if not relative_path:
        return None
    if relative_path.startswith("/") or ":" in Path(relative_path).parts[0]:
        return None

    workspace_root = Path(workspace).expanduser().resolve()
    target = (workspace_root / relative_path).resolve()
    try:
        target.relative_to(workspace_root)
    except ValueError:
        return None
    if not target.is_file():
        return None

    mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if mime_type not in supported_mime_types:
        return None
    b64 = base64.b64encode(target.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def resolve_media_items(
    *,
    current_items: list[str] | None,
    workspace_resolver: Callable[[], Path] | None,
    media_path: str = "",
    media_label: str,
    supported_mime_types: set[str] | frozenset[str],
) -> tuple[list[str], str | None]:
    """Resolve media from either current turn attachments or a saved workspace path."""
    if not media_path.strip():
        return list(current_items or []), None
    if workspace_resolver is None:
        return [], f"Error: saved {media_label} lookup is unavailable because no session workspace is active."
    try:
        media = load_saved_media_data_url(
            workspace_resolver(),
            media_path,
            supported_mime_types=supported_mime_types,
        )
    except OSError as exc:
        return [], f"Error: failed to read saved {media_label} '{media_path}': {exc}"
    if media is None:
        return [], f"Error: saved {media_label} '{media_path}' was not found or is not a supported {media_label} file."
    return [media], None
