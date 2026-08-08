"""Filesystem persistence for inbound media attachments."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ...modules.media.inbound import (
    INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON,
    decode_data_url,
)
from opensprite.core.logging import logger


@dataclass(frozen=True)
class InboundMediaPersistResult:
    files: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


class InboundMediaPersistence:
    """Persist media attached to agent turns."""

    def __init__(
        self,
        *,
        workspace_for_session: Callable[[str], Path],
    ):
        self._workspace_for_session = workspace_for_session

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

        workspace = self._workspace_for_session(session_id)
        media_dir = workspace / directory_name
        saved_files: list[str] = []
        events: list[dict[str, Any]] = []

        for index, item in enumerate(media_items, start=1):
            decoded = decode_data_url(item, media_prefix)
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
                events.append(
                    {
                        "media_type": media_prefix,
                        "status": "failed",
                        "index": index,
                        "mime_type": mime_type,
                        "error": str(exc),
                    }
                )
                logger.warning(
                    "[{}] inbound.{}.persist.failed | index={} error={}",
                    session_id,
                    media_prefix,
                    index,
                    exc,
                )

        return InboundMediaPersistResult(files=saved_files, events=events)
