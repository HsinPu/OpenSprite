"""Bounded, read-only OpenRouter model discovery."""

from __future__ import annotations

import asyncio
import json
from typing import Final

import httpx

from ..models import ErrorCode, OpenRouterModel, OpenRouterModelListResponse
from .adapters import ProviderValidationError

OPENROUTER_MODELS_URL: Final = "https://openrouter.ai/api/v1/models/user"
MAX_OPENROUTER_MODELS_RESPONSE_BYTES: Final = 4 * 1024 * 1024
MAX_OPENROUTER_MODELS: Final = 1000


class OpenRouterModelDiscovery:
    """Fetch and sanitize the connected OpenRouter account's model list."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list_models(
        self,
        api_key: str,
    ) -> OpenRouterModelListResponse:
        failure: ErrorCode | None = None
        status: int | None = None
        response_content: bytes | None = None
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with asyncio.timeout(30.0):
                async with self._client.stream(
                    "GET",
                    OPENROUTER_MODELS_URL,
                    headers=headers,
                    timeout=30.0,
                    follow_redirects=False,
                ) as response:
                    status = response.status_code
                    if 200 <= status < 300:
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            if (
                                len(content) + len(chunk)
                                > MAX_OPENROUTER_MODELS_RESPONSE_BYTES
                            ):
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
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
        if response_content is None:
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)

        try:
            payload: object = json.loads(response_content)
        except (TypeError, ValueError):
            raise ProviderValidationError(
                ErrorCode.PROVIDER_UNREACHABLE
            ) from None

        if type(payload) is not dict or type(payload.get("data")) is not list:
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)

        models: list[OpenRouterModel] = []
        seen_ids: set[str] = set()
        for record in payload["data"]:
            model = self._usable_model(record)
            if model is None or model.id in seen_ids:
                continue
            seen_ids.add(model.id)
            models.append(model)

        if not models or len(models) > MAX_OPENROUTER_MODELS:
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)

        models.sort(key=lambda model: (model.name.casefold(), model.id))
        return OpenRouterModelListResponse(models=models)

    @staticmethod
    def _usable_model(record: object) -> OpenRouterModel | None:
        if type(record) is not dict:
            return None

        model_id = record.get("id")
        name = record.get("name")
        architecture = record.get("architecture")
        context_length = record.get("context_length")
        top_provider = record.get("top_provider")
        if (
            type(model_id) is not str
            or not 1 <= len(model_id) <= 256
            or type(name) is not str
            or not 1 <= len(name) <= 256
            or type(architecture) is not dict
            or type(context_length) is not int
            or isinstance(context_length, bool)
            or not 1 <= context_length <= 4_000_000
        ):
            return None

        input_modalities = architecture.get("input_modalities")
        output_modalities = architecture.get("output_modalities")
        if (
            type(input_modalities) is not list
            or type(output_modalities) is not list
            or "text" not in input_modalities
            or "text" not in output_modalities
        ):
            return None

        max_output_tokens: int | None = None
        if type(top_provider) is dict:
            candidate = top_provider.get("max_completion_tokens")
            if (
                type(candidate) is int
                and not isinstance(candidate, bool)
                and 1 <= candidate <= context_length
            ):
                max_output_tokens = candidate

        return OpenRouterModel(
            id=model_id,
            name=name,
            contextWindowTokens=context_length,
            maxOutputTokens=max_output_tokens,
        )
