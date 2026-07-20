"""Search store abstractions for per-chat retrieval."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

HISTORY_SEARCH_TOOL_NAME = "search_history"


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


class SearchStore(ABC):
    """Abstract search index used for per-chat retrieval."""

    @abstractmethod
    async def sync_from_storage(self) -> None:
        """Backfill any missing records from persistent storage."""

    @abstractmethod
    async def index_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
        created_at: float | None = None,
    ) -> None:
        """Index one conversation message for history search."""

    @abstractmethod
    async def search_history(self, session_id: str, query: str, limit: int = 5) -> list[SearchHit]:
        """Search conversation history within a single chat."""

    @abstractmethod
    async def clear_session(self, session_id: str) -> None:
        """Remove all indexed data for a chat."""
