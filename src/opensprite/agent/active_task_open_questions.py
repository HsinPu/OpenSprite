"""Shared open-question sentinel handling for ACTIVE_TASK state."""

from __future__ import annotations


OPEN_QUESTIONS_CLEAR_SENTINEL = "none"


def clear_open_questions() -> list[str]:
    return [OPEN_QUESTIONS_CLEAR_SENTINEL]


def normalize_open_questions(values: list[object] | tuple[object, ...] | None) -> list[str] | None:
    if values is None:
        return None
    questions = [str(item).strip() for item in values if str(item).strip()]
    if any(item.lower() == OPEN_QUESTIONS_CLEAR_SENTINEL for item in questions):
        return clear_open_questions()
    return questions
