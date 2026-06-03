"""Shared markers for context-compaction handoff messages."""

from __future__ import annotations


COMPACTED_CONVERSATION_STATE_HEADING = "# Compacted Conversation State"
COMPACTED_TASK_STATE_HEADING = "# Compacted Task State"
COMPACTION_HANDOFF_HEADINGS = (
    COMPACTED_CONVERSATION_STATE_HEADING,
    COMPACTED_TASK_STATE_HEADING,
)

LLM_COMPACTION_TOO_LARGE_REASON = "llm_too_large"
LLM_COMPACTION_CONFIG_MISSING_REASON = "llm_config_missing"
LLM_COMPACTION_NO_BODY_REASON = "no_body"
LLM_COMPACTION_NO_PROMPT_REASON = "no_prompt"
LLM_COMPACTION_ERROR_REASON = "llm_error"
LLM_COMPACTION_EMPTY_REASON = "llm_empty"


def contains_compaction_handoff(content: str | None) -> bool:
    text = str(content or "")
    return any(heading in text for heading in COMPACTION_HANDOFF_HEADINGS)
