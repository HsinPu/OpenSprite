"""Shared fallback reasons for LLM-assisted resolution steps."""

from __future__ import annotations


LLM_UNAVAILABLE_REASON_PREFIX = "llm unavailable"
LLM_FAILED_REASON_PREFIX = "llm failed"
LLM_LOW_CONFIDENCE_REASON_PREFIX = "llm confidence too low"

TASK_CONTEXT_RESOLUTION_PURPOSE = "task context was not inferred"
TASK_OBJECTIVE_RESOLUTION_PURPOSE = "objective was not enriched"


def llm_unavailable_reason(purpose: str) -> str:
    return _resolution_reason(LLM_UNAVAILABLE_REASON_PREFIX, purpose)


def llm_failed_reason(purpose: str) -> str:
    return _resolution_reason(LLM_FAILED_REASON_PREFIX, purpose)


def llm_low_confidence_reason(confidence: float, purpose: str) -> str:
    return f"{LLM_LOW_CONFIDENCE_REASON_PREFIX} ({confidence:.2f}); {purpose}"


def _resolution_reason(prefix: str, purpose: str) -> str:
    return f"{prefix}; {purpose}"
