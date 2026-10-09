"""Canonical provenance and coverage validation, without prompt construction."""
from dataclasses import dataclass
import hashlib
import json

from .plugin import ConversationCompaction, Message


@dataclass(frozen=True, slots=True)
class SummaryCoverage:
    source_hash: str
    first_sequence: int
    through_sequence: int


def summary_coverage(previous: ConversationCompaction | None, messages: tuple[Message, ...]) -> SummaryCoverage:
    if not messages or messages[0].sequence != (1 if previous is None else previous.covers_through_sequence + 1):
        raise ValueError("summary must extend complete previous coverage")
    if any(left.sequence + 1 != right.sequence for left, right in zip(messages, messages[1:])):
        raise ValueError("summary source must be contiguous")
    canonical = {
        "previous": None if previous is None else {
            "coversThroughSequence": previous.covers_through_sequence,
            "sourceHash": previous.source_hash, "summary": previous.summary,
        },
        "messages": [{"sequence": item.sequence, "role": item.role, "content": item.content} for item in messages],
    }
    encoded = json.dumps(canonical, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    return SummaryCoverage(hashlib.sha256(encoded.encode("utf-8")).hexdigest(), messages[0].sequence, messages[-1].sequence)
