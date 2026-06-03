"""Shared markers for context-compaction handoff messages."""

from __future__ import annotations


COMPACTED_CONVERSATION_STATE_HEADING = "# Compacted Conversation State"
COMPACTED_TASK_STATE_HEADING = "# Compacted Task State"
COMPACTION_HANDOFF_HEADINGS = (
    COMPACTED_CONVERSATION_STATE_HEADING,
    COMPACTED_TASK_STATE_HEADING,
)


def contains_compaction_handoff(content: str | None) -> bool:
    text = str(content or "")
    return any(heading in text for heading in COMPACTION_HANDOFF_HEADINGS)
