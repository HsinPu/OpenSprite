"""Credential-on-demand routing into the fixed native Provider adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping

import httpx

from opensprite_backend.credentials import CredentialStore, CredentialStoreError
from opensprite_backend.providers.operation_locks import ProviderOperationLocks

from .anthropic import AnthropicInferenceAdapter
from .gateway import ModelGatewayError, ProviderInferenceAdapter
from .models import InferenceFailure, ModelRequest, ModelStreamEvent
from .openai import OpenAIInferenceAdapter
from .openrouter import OpenRouterInferenceAdapter
from .sse import StreamFormatError


class NativeModelGateway:
    """Read one encrypted credential only for the duration of one model call."""

    def __init__(
        self,
        credentials: CredentialStore,
        http_client: httpx.AsyncClient,
        operation_locks: ProviderOperationLocks,
        *,
        adapters: Mapping[str, ProviderInferenceAdapter] | None = None,
    ) -> None:
        self._credentials = credentials
        self._locks = operation_locks
        self._adapters: dict[str, ProviderInferenceAdapter] = (
            dict(adapters)
            if adapters is not None
            else {
                "openai": OpenAIInferenceAdapter(http_client),
                "anthropic": AnthropicInferenceAdapter(http_client),
                "openrouter": OpenRouterInferenceAdapter(http_client),
            }
        )
        if set(self._adapters) != {"openai", "anthropic", "openrouter"}:
            raise ValueError("native gateway requires the fixed Provider catalog")

    async def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[ModelStreamEvent]:
        adapter = self._adapters[request.provider_id]
        async with self._locks.hold(request.provider_id):
            try:
                api_key = await asyncio.to_thread(
                    self._credentials.get,
                    request.provider_id,
                )
            except CredentialStoreError as error:
                raise ModelGatewayError(
                    InferenceFailure.CREDENTIAL_STORE_UNAVAILABLE
                ) from error
            except Exception as error:
                raise ModelGatewayError(
                    InferenceFailure.CREDENTIAL_STORE_UNAVAILABLE
                ) from error
            if api_key is None:
                raise ModelGatewayError(
                    InferenceFailure.PROVIDER_NOT_CONNECTED
                )
            try:
                async for event in adapter.stream(request, api_key):
                    yield event
            except ModelGatewayError:
                raise
            except (StreamFormatError, TypeError, ValueError) as error:
                raise ModelGatewayError(
                    InferenceFailure.INVALID_PROVIDER_RESPONSE
                ) from error
            finally:
                api_key = ""
