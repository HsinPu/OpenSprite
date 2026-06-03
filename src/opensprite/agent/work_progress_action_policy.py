"""Shared next-action policy for structured work progress."""

from __future__ import annotations


NEXT_ACTION_FINALIZE = "finalize"
NEXT_ACTION_STOP_BUDGET_EXHAUSTED = "stop_budget_exhausted"
NEXT_ACTION_STOP_NO_PROGRESS = "stop_no_progress"
NEXT_ACTION_CONTINUE_VERIFICATION = "continue_verification"
NEXT_ACTION_COLLECT_REVIEW_EVIDENCE = "collect_review_evidence"
NEXT_ACTION_ADDRESS_REVIEW_FINDINGS = "address_review_findings"
NEXT_ACTION_CONTINUE_REVIEW = "continue_review"
NEXT_ACTION_CONTINUE_WORK = "continue_work"

REVIEW_FOLLOW_UP_NEXT_ACTIONS = frozenset(
    {
        NEXT_ACTION_COLLECT_REVIEW_EVIDENCE,
        NEXT_ACTION_ADDRESS_REVIEW_FINDINGS,
    }
)
REVIEW_PHASE_NEXT_ACTIONS = frozenset(
    {
        NEXT_ACTION_CONTINUE_REVIEW,
        *REVIEW_FOLLOW_UP_NEXT_ACTIONS,
    }
)


def normalize_next_action(value: str | None) -> str:
    return str(value or "").strip()


def is_verification_next_action(value: str | None) -> bool:
    return normalize_next_action(value) == NEXT_ACTION_CONTINUE_VERIFICATION


def is_continue_work_next_action(value: str | None) -> bool:
    return normalize_next_action(value) == NEXT_ACTION_CONTINUE_WORK


def is_review_follow_up_next_action(value: str | None) -> bool:
    return normalize_next_action(value) in REVIEW_FOLLOW_UP_NEXT_ACTIONS


def is_review_phase_next_action(value: str | None) -> bool:
    return normalize_next_action(value) in REVIEW_PHASE_NEXT_ACTIONS
