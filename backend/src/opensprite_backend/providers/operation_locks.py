"""Shared process-local serialization for one Provider's credential operations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ..models import ProviderId
from .catalog_models import valid_provider_id


_PROVIDERS = {"openai", "anthropic", "openrouter"}


class ProviderOperationLocks:
    """Own one asyncio lock per fixed Provider for one desktop process."""

    def __init__(self) -> None:
        self._locks = {
            provider_id: asyncio.Lock()
            for provider_id in sorted(_PROVIDERS)
        }
        self._generations = {provider_id: 0 for provider_id in _PROVIDERS}

    @asynccontextmanager
    async def hold(self, provider_id: ProviderId) -> AsyncIterator[None]:
        if not valid_provider_id(provider_id):
            raise ValueError("unsupported provider lock")
        async with self._locks.setdefault(provider_id, asyncio.Lock()):
            yield

    def generation(self, provider_id: ProviderId) -> int:
        if not valid_provider_id(provider_id):
            raise ValueError("unsupported provider lock")
        return self._generations.get(provider_id, 0)

    def invalidate(self, provider_id: ProviderId) -> None:
        if not valid_provider_id(provider_id):
            raise ValueError("unsupported provider lock")
        self._generations[provider_id] = self._generations.get(provider_id, 0) + 1
