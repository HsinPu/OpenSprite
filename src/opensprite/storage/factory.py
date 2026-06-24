"""Storage provider factory."""

from __future__ import annotations

from ..config import Config
from .base import StorageProvider
from .memory import MemoryStorage


def create_storage(config: Config) -> StorageProvider:
    """Create the configured storage provider."""

    storage_type = config.storage.type

    if storage_type == "memory":
        return MemoryStorage()
    if storage_type == "sqlite":
        from .sqlite import SQLiteStorage

        return SQLiteStorage(db_path=config.storage.path)

    raise ValueError(f"Unsupported storage provider: {storage_type}")
