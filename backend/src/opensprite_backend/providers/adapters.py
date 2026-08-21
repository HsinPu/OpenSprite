"""Fixed, sanitized HTTP adapters for provider credential validation."""

from __future__ import annotations

import asyncio
import json
from typing import Final, Protocol

import httpx

from ..models import ErrorCode, OpenRouterModelListResponse, ProviderId

PROVIDER_TIMEOUT_SECONDS: Final = 30.0
MAX_PROVIDER_RESPONSE_BYTES: Final = 1024 * 1024
OPENAI_MODELS_URL: Final = "https://api.openai.com/v1/models"
ANTHROPIC_MODELS_URL: Final = "https://api.anthropic.com/v1/models?limit=1"
OPENROUTER_KEY_URL: Final = "https://openrouter.ai/api/v1/key"


class ProviderValidationError(Exception):
    """A provider failure reduced to its public, non-secret error code."""

    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class ProviderAdapter(Protocol):
    async def validate(self, api_key: str) -> None: ...


class _HttpProviderAdapter:
    def __init__(
        self,
        client: httpx.AsyncClient,
        url: str,
        header_name: str,
        header_value_prefix: str = "",
        extra_headers: dict[str, str] | None = None,
        expected_data_type: type[object] = list,
    ) -> None:
        self._client = client
        self._url = url
        self._header_name = header_name
        self._header_value_prefix = header_value_prefix
        self._extra_headers = extra_headers or {}
        self._expected_data_type = expected_data_type

    async def validate(self, api_key: str) -> None:
        failure: ErrorCode | None = None
        status: int | None = None
        response_content: bytes | None = None
        headers = {
            self._header_name: f"{self._header_value_prefix}{api_key}",
            **self._extra_headers,
        }
        try:
            async with asyncio.timeout(PROVIDER_TIMEOUT_SECONDS):
                async with self._client.stream(
                    "GET",
                    self._url,
                    headers=headers,
                    timeout=PROVIDER_TIMEOUT_SECONDS,
                    follow_redirects=False,
                ) as response:
                    status = response.status_code
                    if 200 <= status < 300:
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(content) + len(chunk) > MAX_PROVIDER_RESPONSE_BYTES:
                                failure = ErrorCode.PROVIDER_UNREACHABLE
                                break
                            content.extend(chunk)
                        if failure is None:
                            response_content = bytes(content)
        except (TimeoutError, httpx.TimeoutException):
            failure = ErrorCode.PROVIDER_TIMEOUT
        except Exception:
            failure = ErrorCode.PROVIDER_UNREACHABLE

        if failure is not None:
            raise ProviderValidationError(failure)
        if status is None:
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)

        if status in {401, 403}:
            raise ProviderValidationError(ErrorCode.INVALID_CREDENTIALS)
        if status == 429:
            raise ProviderValidationError(ErrorCode.PROVIDER_RATE_LIMITED)
        if status >= 500 or not 200 <= status < 300:
            # Other non-success responses are conservatively treated as an
            # unavailable validation service, not proof of credential failure.
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)

        payload: object = None
        malformed = False
        try:
            payload = json.loads(response_content)
        except (TypeError, ValueError):
            malformed = True
        if (
            malformed
            or type(payload) is not dict
            or type(payload.get("data")) is not self._expected_data_type
        ):
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)


class ProviderValidator:
    """Deny-by-default catalog containing only approved provider adapters."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        from .openrouter_models import OpenRouterModelDiscovery

        self._adapters: dict[ProviderId, ProviderAdapter] = {
            "openai": _HttpProviderAdapter(
                client,
                OPENAI_MODELS_URL,
                "Authorization",
                "Bearer ",
            ),
            "anthropic": _HttpProviderAdapter(
                client,
                ANTHROPIC_MODELS_URL,
                "x-api-key",
                extra_headers={"anthropic-version": "2023-06-01"},
            ),
            "openrouter": _HttpProviderAdapter(
                client,
                OPENROUTER_KEY_URL,
                "Authorization",
                "Bearer ",
                expected_data_type=dict,
            ),
        }
        self._openrouter_models = OpenRouterModelDiscovery(client)

    async def validate(self, provider_id: ProviderId, api_key: str) -> None:
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            raise ProviderValidationError(ErrorCode.UNSUPPORTED_PROVIDER)
        await adapter.validate(api_key)

    async def list_openrouter_models(
        self,
        api_key: str,
    ) -> OpenRouterModelListResponse:
        return await self._openrouter_models.list_models(api_key)
