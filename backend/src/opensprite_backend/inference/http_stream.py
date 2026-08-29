"""Shared bounded HTTP/SSE transport for native inference adapters."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Final

import httpx

from .gateway import ModelGatewayError
from .models import InferenceFailure
from .sse import StreamFormatError, iter_sse_data


INFERENCE_TIMEOUT_SECONDS: Final = 300.0
_MAX_ERROR_BODY_BYTES: Final = 65_536
_CONTEXT_LIMIT_CODES: Final = {
    "context_length_exceeded",
    "context_window_exceeded",
    "input_too_long",
    "prompt_too_long",
}
_CONTEXT_LIMIT_MESSAGES: Final = (
    "context length exceeded",
    "context limit exceeded",
    "context window exceeded",
    "exceeds the context window",
    "maximum context length",
    "prompt is too long",
    "prompt too long",
    "too many input tokens",
)
_REQUEST_TIMEOUT = httpx.Timeout(
    connect=30.0,
    read=INFERENCE_TIMEOUT_SECONDS,
    write=30.0,
    pool=30.0,
)


class NativeHttpAdapter:
    def __init__(self, client: httpx.AsyncClient, url: str) -> None:
        self._client = client
        self._url = url

    async def payloads(
        self,
        *,
        headers: dict[str, str],
        body: dict[str, object],
    ) -> AsyncIterator[str]:
        try:
            async with asyncio.timeout(INFERENCE_TIMEOUT_SECONDS):
                async with self._client.stream(
                    "POST",
                    self._url,
                    headers=headers,
                    json=body,
                    timeout=_REQUEST_TIMEOUT,
                    follow_redirects=False,
                ) as response:
                    await self._raise_for_response(response)
                    async for payload in iter_sse_data(response):
                        yield payload
        except ModelGatewayError:
            raise
        except (TimeoutError, httpx.TimeoutException) as error:
            raise ModelGatewayError(InferenceFailure.PROVIDER_TIMEOUT) from error
        except StreamFormatError as error:
            raise ModelGatewayError(
                InferenceFailure.INVALID_PROVIDER_RESPONSE
            ) from error
        except httpx.HTTPError as error:
            raise ModelGatewayError(
                InferenceFailure.PROVIDER_UNREACHABLE
            ) from error
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise ModelGatewayError(
                InferenceFailure.PROVIDER_UNREACHABLE
            ) from error

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if 200 <= status < 300:
            return
        if status in {401, 403}:
            raise ModelGatewayError(InferenceFailure.INVALID_CREDENTIALS)
        if status == 429:
            raise ModelGatewayError(InferenceFailure.PROVIDER_RATE_LIMITED)
        if status in {408, 504}:
            raise ModelGatewayError(InferenceFailure.PROVIDER_TIMEOUT)
        if status == 413:
            raise ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)
        raise ModelGatewayError(InferenceFailure.PROVIDER_UNREACHABLE)

    @classmethod
    async def _raise_for_response(cls, response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status in {400, 422}:
            body = await cls._read_bounded_error_body(response)
            if body is not None and cls._is_context_limit_error(body):
                raise ModelGatewayError(InferenceFailure.CONTEXT_LIMIT_EXCEEDED)
        cls._raise_for_status(status)

    @staticmethod
    async def _read_bounded_error_body(response: httpx.Response) -> bytes | None:
        body = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=8_192):
            if len(body) + len(chunk) > _MAX_ERROR_BODY_BYTES:
                return None
            body.extend(chunk)
        return bytes(body)

    @staticmethod
    def _is_context_limit_error(body: bytes) -> bool:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        if type(payload) is not dict or type(payload.get("error")) is not dict:
            return False
        error = payload["error"]
        for field in ("code", "type"):
            value = error.get(field)
            if isinstance(value, str) and value.lower() in _CONTEXT_LIMIT_CODES:
                return True
        message = error.get("message")
        if not isinstance(message, str):
            return False
        normalized = " ".join(message.lower().split())
        return any(marker in normalized for marker in _CONTEXT_LIMIT_MESSAGES)
