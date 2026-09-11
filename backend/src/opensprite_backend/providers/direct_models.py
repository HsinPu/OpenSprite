"""Bounded discovery for the built-in OpenAI and Anthropic transports."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Literal

import httpx

from ..inference.capabilities import ModelCapability, fixed_model_capability
from ..models import ErrorCode
from .adapters import ProviderValidationError

DirectProvider = Literal["openai", "anthropic"]
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_PAGES = 100


class DirectModelDiscovery:
    """Never infer capacity or tool support from a newly discovered model ID."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list_models(
        self, provider_id: DirectProvider, api_key: str,
    ) -> tuple[ModelCapability, ...]:
        if provider_id not in {"openai", "anthropic"}:
            raise ProviderValidationError(ErrorCode.UNSUPPORTED_PROVIDER)
        try:
            async with asyncio.timeout(30):
                return await self._collect(provider_id, api_key)
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderValidationError(ErrorCode.PROVIDER_TIMEOUT) from None
        except ProviderValidationError:
            raise
        except Exception:
            # Do not expose request URLs, headers, response bodies, or credentials.
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE) from None

    async def _collect(
        self, provider_id: DirectProvider, api_key: str,
    ) -> tuple[ModelCapability, ...]:
        url = ("https://api.openai.com/v1/models" if provider_id == "openai"
               else "https://api.anthropic.com/v1/models")
        headers = ({"Authorization": f"Bearer {api_key}"} if provider_id == "openai"
                   else {"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        params: dict[str, str] = {} if provider_id == "openai" else {"limit": "1000"}
        models: dict[str, ModelCapability] = {}
        cursors: set[str] = set()
        total_bytes = 0
        for _ in range(MAX_PAGES):
            async with self._client.stream(
                "GET", url, headers=headers, params=params,
                timeout=30, follow_redirects=False,
            ) as response:
                if response.status_code in {401, 403}:
                    raise ProviderValidationError(ErrorCode.INVALID_CREDENTIALS)
                if response.status_code == 429:
                    raise ProviderValidationError(ErrorCode.PROVIDER_RATE_LIMITED)
                if not 200 <= response.status_code < 300:
                    raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > MAX_RESPONSE_BYTES:
                        raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
                    content.extend(chunk)
            payload = json.loads(content)
            if type(payload) is not dict or type(payload.get("data")) is not list:
                raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
            for record in payload["data"]:
                if type(record) is not dict:
                    raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
                model_id = record.get("id")
                if type(model_id) is not str or not 1 <= len(model_id) <= 256 or model_id.strip() != model_id:
                    raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
                if provider_id == "openai" and not _openai_text_candidate(model_id):
                    continue
                name = record.get("display_name", model_id)
                if type(name) is not str or not 1 <= len(name.strip()) <= 256:
                    raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
                models[model_id] = fixed_model_capability(provider_id, model_id) or ModelCapability(
                    provider_id=provider_id, model_id=model_id, name=name.strip(),
                    context_window_tokens=8192, max_output_tokens=2048,
                    supports_tools=False,
                )
            if provider_id == "openai":
                break
            has_more = payload.get("has_more")
            if type(has_more) is not bool:
                raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
            if not has_more:
                break
            cursor = payload.get("last_id")
            page_ids = {record["id"] for record in payload["data"]}
            if type(cursor) is not str or cursor not in page_ids or cursor in cursors:
                raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
            cursors.add(cursor)
            params["after_id"] = cursor
        else:
            raise ProviderValidationError(ErrorCode.PROVIDER_UNREACHABLE)
        return tuple(sorted(models.values(), key=lambda model: (model.name.casefold(), model.model_id)))


def _openai_text_candidate(model_id: str) -> bool:
    """Conservative discovery filter, not a guarantee of Responses compatibility."""
    base = model_id.split(":", 2)[1] if model_id.startswith("ft:") and ":" in model_id[3:] else model_id
    if not re.match(r"^(?:gpt-|chatgpt-|o[1-9](?:-|$))", base):
        return False
    return not any(part in base for part in (
        "audio", "realtime", "transcri", "tts", "image", "search", "instruct",
    ))
