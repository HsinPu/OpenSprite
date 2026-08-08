"""Application composition for persistence adapters."""

from __future__ import annotations

from ..config import Config
from ..core.ports.storage import StorageProvider
from ..integrations.persistence import memory as memory_persistence
from ..integrations.persistence.sqlite import storage as sqlite_persistence


def create_storage(config: Config) -> StorageProvider:
    """Create the configured storage provider."""

    storage_type = config.storage.type

    if storage_type == "memory":
        return memory_persistence.MemoryStorage()
    if storage_type == "sqlite":
        return sqlite_persistence.SQLiteStorage(db_path=config.storage.path)

    raise ValueError(f"Unsupported storage provider: {storage_type}")
