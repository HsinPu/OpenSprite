"""Search store factory."""

from __future__ import annotations

from ..config import Config
from .base import SearchStore
from .embedding_factory import create_search_embedding_provider


def create_search_store(config: Config) -> SearchStore | None:
    """Create the optional search store."""

    if not getattr(config, "search", None) or not config.search.enabled:
        return None

    search_backend = getattr(config.search, "backend", "sqlite")
    if search_backend == "sqlite":
        if config.storage.type != "sqlite":
            raise ValueError('search.backend="sqlite" requires storage.type="sqlite"')

        from .sqlite_store import SQLiteSearchStore

        embedding_provider = create_search_embedding_provider(config)
        return SQLiteSearchStore(
            path=config.storage.path,
            history_top_k=config.search.history_top_k,
            embedding_provider=embedding_provider,
            hybrid_candidate_count=config.search.embedding.candidate_count,
            embedding_candidate_strategy=config.search.embedding.candidate_strategy,
            vector_backend=config.search.embedding.vector_backend,
            vector_candidate_count=config.search.embedding.vector_candidate_count,
            retry_failed_on_startup=config.search.embedding.retry_failed_on_startup,
        )

    raise ValueError(f"Unsupported search backend: {search_backend}")
