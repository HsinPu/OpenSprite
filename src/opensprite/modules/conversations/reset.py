"""Session conversation-history reset service."""

from __future__ import annotations

from typing import Awaitable, Callable

from ...core.ports.search import SearchStore
from ...core.ports.storage import StorageProvider
from opensprite.core.logging import logger


class HistoryResetService:
    """Clears session history and related per-session derived state."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        history_search_store: SearchStore | None,
        clear_session_artifacts: Callable[[str], Awaitable[None]],
    ):
        self.storage = storage
        self.history_search_store = history_search_store
        self._clear_session_artifacts = clear_session_artifacts

    async def reset(self, session_id: str) -> None:
        """Clear one session from storage and derived indexes."""
        await self._clear_one(session_id)

    async def _clear_one(self, session_id: str) -> None:
        await self._clear_session_artifacts(session_id)
        await self.storage.clear_messages(session_id)
        if self.history_search_store is None:
            return
        try:
            await self.history_search_store.clear_session(session_id)
        except Exception as e:
            logger.warning("[{}] Failed to clear search index: {}", session_id, e)
