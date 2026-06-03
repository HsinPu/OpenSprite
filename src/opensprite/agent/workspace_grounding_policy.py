"""Shared policy for workspace-grounded final answers."""

from __future__ import annotations

import re


WORKSPACE_LOCATION_SYMBOL_RE = re.compile(r"\b(?:function|class|method|symbol)\s+[`'\"]?[\w.:-]+")
WORKSPACE_LOCATION_QUOTED_TOKEN_RE = re.compile(r"[`'\"][\w.:-]+[`'\"]")


def contains_workspace_location_clue(response_text: str | None, *, has_workspace_path: bool = False) -> bool:
    """Return whether a final answer identifies a concrete workspace location."""
    if has_workspace_path:
        return True
    normalized = str(response_text or "").strip().lower()
    if not normalized:
        return False
    if WORKSPACE_LOCATION_SYMBOL_RE.search(normalized):
        return True
    return bool(WORKSPACE_LOCATION_QUOTED_TOKEN_RE.search(normalized))
