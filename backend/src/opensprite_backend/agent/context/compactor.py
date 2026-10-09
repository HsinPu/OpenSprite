"""Canonical, hashed historical data. The Loop supplies summary instructions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from opensprite_backend.conversations.models import (
    ConversationCompaction,
    Message,
)


@dataclass(frozen=True, slots=True)
class CompactionSource:
    prompt: str
    source_hash: str
    covers_through_sequence: int


def prepare_compaction_source(
    previous: ConversationCompaction | None,
    messages: tuple[Message, ...],
) -> CompactionSource:
    if not messages:
        raise ValueError("compaction source must include messages")
    if any(
        index > 0 and messages[index - 1].sequence + 1 != message.sequence
        for index, message in enumerate(messages)
    ):
        raise ValueError("compaction messages must be contiguous")
    if previous is not None and messages[0].sequence != (
        previous.covers_through_sequence + 1
    ):
        raise ValueError("compaction must continue previous coverage")

    canonical = {
        "previous": None
        if previous is None
        else {
            "coversThroughSequence": previous.covers_through_sequence,
            "sourceHash": previous.source_hash,
            "summary": previous.summary,
        },
        "messages": [
            {
                "sequence": item.sequence,
                "role": item.role,
                "content": item.content,
            }
            for item in messages
        ],
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    source_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    prompt = f"HISTORICAL_DATA_JSON\n{encoded}\nEND_HISTORICAL_DATA"
    return CompactionSource(
        prompt=prompt,
        source_hash=source_hash,
        covers_through_sequence=messages[-1].sequence,
    )
