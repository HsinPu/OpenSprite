"""Search store factory."""

from __future__ import annotations

from ..config import Config
from .base import SearchStore


def create_history_search_store(config: Config) -> SearchStore | None:
    """Create the optional local conversation-history search store."""

    if not config.history_search.enabled:
        return None

    if config.storage.type != "sqlite":
        raise ValueError('history_search requires storage.type="sqlite"')

    from .sqlite_store import SQLiteSearchStore

    return SQLiteSearchStore(
        path=config.storage.path,
        history_top_k=config.history_search.history_top_k,
    )
