"""Conversation-history search contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchHit:
    """Single local conversation-history match."""

    id: str
    session_id: str
    content: str
    created_at: float
    score: float | None = None
    role: str | None = None
    tool_name: str | None = None
