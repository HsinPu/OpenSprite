"""Serialize only validated semantic Run events into SSE frames."""

from __future__ import annotations

import json
from datetime import UTC

from opensprite_backend.conversations.models import RunEvent


def run_event_frame(event: RunEvent) -> str:
    created_at = event.created_at.astimezone(UTC).isoformat().replace(
        "+00:00",
        "Z",
    )
    payload = json.dumps(
        {
            "sequence": event.sequence,
            "type": event.type.value,
            "runId": event.run_id,
            "conversationId": event.conversation_id,
            "createdAt": created_at,
            "data": event.data,
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return (
        f"id: {event.sequence}\n"
        f"event: {event.type.value}\n"
        f"data: {payload}\n\n"
    )
