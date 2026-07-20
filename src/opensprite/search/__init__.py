"""SQLite-backed conversation history search."""

from .base import SearchHit, SearchStore

__all__ = ["SearchHit", "SearchStore", "SQLiteSearchStore"]


def __getattr__(name: str):
    """Lazily import the SQLite store to avoid import cycles."""
    if name == "SQLiteSearchStore":
        from .sqlite_store import SQLiteSearchStore

        return SQLiteSearchStore
    raise AttributeError(f"module 'opensprite.search' has no attribute {name!r}")
