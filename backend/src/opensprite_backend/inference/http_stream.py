"""Shared bounded HTTP/SSE transport for native inference adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Final

import httpx

from .gateway import ModelGatewayError
from .models import InferenceFailure
from .sse import StreamFormatError, iter_sse_data


INFERENCE_TIMEOUT_SECONDS: Final = 300.0
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
                    self._raise_for_status(response.status_code)
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
        raise ModelGatewayError(InferenceFailure.PROVIDER_UNREACHABLE)
