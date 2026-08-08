"""Shared validation and rendering rules for mutable skill-like documents."""

from __future__ import annotations

import re
from collections import Counter


MIN_SKILL_DESCRIPTION_LEN = 80
MIN_SKILL_DESCRIPTION_WORDS = 16
MIN_SKILL_DESCRIPTION_CONTENT_WORDS = 12
MAX_SKILL_DESCRIPTION_TOKEN_DOMINANCE = 0.38
MIN_SKILL_BODY_LEN = 40
MAX_SKILL_ID_LEN = 64

_DESCRIPTION_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "nor",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "as",
        "if",
        "so",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
    }
)
_SKILL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def validate_skill_id(skill_name: str) -> str | None:
    """Validate a stable, filesystem-safe identifier for a mutable document."""
    name = str(skill_name or "").strip()
    if not name:
        return "skill_name is required"
    if "/" in name or "\\" in name or "." in name or ".." in name:
        return f"Invalid skill name '{skill_name}'"
    if len(name) < 2:
        return "skill_name must be at least 2 characters"
    if len(name) > MAX_SKILL_ID_LEN:
        return f"skill_name must be at most {MAX_SKILL_ID_LEN} characters"
    if not _SKILL_ID_PATTERN.match(name):
        return (
            "skill_name must be lowercase ASCII, start with a letter, use hyphens between segments only "
            "(e.g. my-feature, skill-creator-design). Underscores, uppercase, and dots are not allowed."
        )
    return None


def validate_description_for_write(description: str | None, *, action: str) -> str | None:
    """Validate the substantive description required for a mutable document."""
    if description is None:
        return f"description is required for {action}"
    text = str(description).strip()
    if not text:
        return f"description is required for {action}"
    if len(text) < MIN_SKILL_DESCRIPTION_LEN:
        return (
            f"description must be at least {MIN_SKILL_DESCRIPTION_LEN} characters "
            f"(after trim); got {len(text)}. Write a detailed English description (what the skill does and when to use it)."
        )

    words = [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9']*", text)]
    if len(words) < MIN_SKILL_DESCRIPTION_WORDS:
        return (
            f"description must contain at least {MIN_SKILL_DESCRIPTION_WORDS} English words "
            f"(Latin letters); got {len(words)}. Add more detail: what the skill does, when to load it, and typical tasks."
        )

    content_tokens = [word for word in words if word not in _DESCRIPTION_STOPWORDS and len(word) > 2]
    if len(content_tokens) < MIN_SKILL_DESCRIPTION_CONTENT_WORDS:
        return (
            f"description is not detailed enough: need at least {MIN_SKILL_DESCRIPTION_CONTENT_WORDS} "
            "substantive English words (not only articles/prepositions). Explain capabilities and when the agent should use this skill."
        )

    if content_tokens:
        top_count = Counter(content_tokens).most_common(1)[0][1]
        if top_count / len(content_tokens) > MAX_SKILL_DESCRIPTION_TOKEN_DOMINANCE:
            return (
                "description looks too repetitive or padded (same terms dominate). "
                "Rewrite with varied, specific detail about the skill scope and triggers."
            )

    return None


def validate_body_for_write(body: str | None, *, action: str) -> str | None:
    """Validate the instruction body required for a mutable document."""
    if body is None:
        return f"body is required for {action}"
    text = str(body).strip()
    if len(text) < MIN_SKILL_BODY_LEN:
        return (
            f"body must be at least {MIN_SKILL_BODY_LEN} characters (after trim); got {len(text)}. "
            "Add imperative instructions for the skill body."
        )
    return None


def build_skill_markdown(skill_name: str, description: str, body: str) -> str:
    """Render a mutable SKILL.md document without changing its established format."""
    desc = (description or "").strip().replace("\n", " ").replace("\r", "")
    body_text = (body or "").strip()
    return f"---\nname: {skill_name}\ndescription: {desc}\n---\n\n{body_text}\n"
