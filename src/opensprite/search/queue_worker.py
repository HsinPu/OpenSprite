"""Search embedding queue worker helpers."""

from __future__ import annotations

import asyncio

from ..utils.log import logger
from .base import SearchStore


def should_start_search_queue_worker(search_store: SearchStore | None) -> bool:
    """Return whether the runtime should start the persistent embedding queue worker."""

    return bool(
        search_store is not None
        and getattr(search_store, "embedding_provider", None) is not None
        and hasattr(search_store, "run_queue")
    )


def start_search_queue_worker(search_store: SearchStore | None) -> asyncio.Task | None:
    """Start the long-running embedding queue worker when embeddings are enabled."""

    if not should_start_search_queue_worker(search_store):
        return None
    logger.info("Starting search embedding queue worker")
    return asyncio.create_task(search_store.run_queue(once=False))
