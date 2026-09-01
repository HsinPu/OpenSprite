"""Shared process-local serialization for one Provider's credential operations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ..models import ProviderId


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
        if provider_id not in _PROVIDERS:
            raise ValueError("unsupported provider lock")
        async with self._locks[provider_id]:
            yield

    def generation(self, provider_id: ProviderId) -> int:
        if provider_id not in _PROVIDERS:
            raise ValueError("unsupported provider lock")
        return self._generations[provider_id]

    def invalidate(self, provider_id: ProviderId) -> None:
        if provider_id not in _PROVIDERS:
            raise ValueError("unsupported provider lock")
        self._generations[provider_id] += 1
