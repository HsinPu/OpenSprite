"""Shared text tokenization policy for task-context heuristics."""

from __future__ import annotations

import re


TASK_TEXT_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")


def task_text_tokens(text: str | None) -> tuple[str, ...]:
    """Return coarse language-neutral tokens for short follow-up heuristics."""
    return tuple(TASK_TEXT_TOKEN_RE.findall(str(text or "")))
