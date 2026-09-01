"""Provider-backed adapter for the Agent model-capability protocol."""

from __future__ import annotations

import asyncio
from time import monotonic

from opensprite_backend.agent.context.capability_resolver import (
    ModelCapabilityNotFound,
    ModelCapabilityProviderError,
)
from opensprite_backend.inference.capabilities import (
    ModelCapability,
    fixed_model_capability,
)
from opensprite_backend.inference.models import InferenceFailure
from opensprite_backend.models import ErrorCode, ProviderId
from opensprite_backend.provider_connections import (
    ProviderConnectionError,
    ProviderConnections,
)
from opensprite_backend.providers.operation_locks import ProviderOperationLocks


class ProviderModelCapabilityResolver:
    def __init__(
        self,
        provider_connections: ProviderConnections,
        *,
        cache_seconds: float = 600.0,
        operation_locks: ProviderOperationLocks | None = None,
    ) -> None:
        if not 1 <= cache_seconds <= 3600:
            raise ValueError("invalid model capability cache lifetime")
        self._provider_connections = provider_connections
        self._cache_seconds = cache_seconds
        self._openrouter_cache: dict[str, ModelCapability] = {}
        self._cache_loaded_at = 0.0
        self._cache_generation: int | None = None
        self._operation_locks = operation_locks
        self._lock = asyncio.Lock()

    async def resolve(
        self,
        provider_id: ProviderId,
        model_id: str,
    ) -> ModelCapability:
        fixed = fixed_model_capability(provider_id, model_id)
        if fixed is not None:
            return fixed
        if provider_id != "openrouter":
            raise ModelCapabilityNotFound
        async with self._lock:
            generation = self._current_generation()
            if generation != self._cache_generation:
                self._openrouter_cache = {}
                self._cache_loaded_at = 0.0
                self._cache_generation = generation
            refreshed = False
            if (
                self._cache_loaded_at == 0.0
                or monotonic() - self._cache_loaded_at >= self._cache_seconds
            ):
                await self._refresh_openrouter_cache()
                refreshed = True
            selected = self._openrouter_cache.get(model_id)
            if selected is None and not refreshed:
                await self._refresh_openrouter_cache()
                selected = self._openrouter_cache.get(model_id)
            if selected is None:
                raise ModelCapabilityNotFound
            return selected

    async def _refresh_openrouter_cache(self) -> None:
        try:
            catalog = await self._provider_connections.list_openrouter_models()
        except ProviderConnectionError as error:
            raise ModelCapabilityProviderError(
                _provider_failure(error.code)
            ) from error
        self._openrouter_cache = {
            item.id: ModelCapability(
                provider_id="openrouter",
                model_id=item.id,
                name=item.name,
                context_window_tokens=item.context_window_tokens,
                max_output_tokens=item.max_output_tokens
                or min(32_768, item.context_window_tokens),
            )
            for item in catalog.models
        }
        self._cache_loaded_at = monotonic()
        self._cache_generation = self._current_generation()

    def _current_generation(self) -> int | None:
        if self._operation_locks is None:
            return None
        return self._operation_locks.generation("openrouter")


def _provider_failure(code: ErrorCode) -> InferenceFailure:
    return {
        ErrorCode.NOT_CONNECTED: InferenceFailure.PROVIDER_NOT_CONNECTED,
        ErrorCode.INVALID_CREDENTIALS: InferenceFailure.INVALID_CREDENTIALS,
        ErrorCode.PROVIDER_RATE_LIMITED: InferenceFailure.PROVIDER_RATE_LIMITED,
        ErrorCode.PROVIDER_TIMEOUT: InferenceFailure.PROVIDER_TIMEOUT,
        ErrorCode.PROVIDER_UNREACHABLE: InferenceFailure.PROVIDER_UNREACHABLE,
        ErrorCode.CREDENTIAL_STORE_UNAVAILABLE: InferenceFailure.CREDENTIAL_STORE_UNAVAILABLE,
    }.get(code, InferenceFailure.PROVIDER_UNREACHABLE)
