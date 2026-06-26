"""Shared helpers for providers backed by the OpenAI-compatible SDK."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import LLMResponse
from .response_utils import coerce_content
from .response_utils import extract_openai_compatible_message
from .response_utils import extract_openai_compatible_tool_calls
from .response_utils import usage_payload


def build_openai_client_kwargs(
    api_key: str,
    *,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
    **extra_kwargs: Any,
) -> dict[str, Any]:
    """Build AsyncOpenAI constructor kwargs while omitting unset optional fields."""
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    if default_headers:
        kwargs["default_headers"] = dict(default_headers)
    kwargs.update({key: value for key, value in extra_kwargs.items() if value is not None})
    return kwargs


class OpenAICompatibleClientMixin:
    """Mixin for providers that rebuild an AsyncOpenAI client from kwargs."""

    _client_kwargs: dict[str, Any]

    def _build_client(self) -> Any:
        from openai import AsyncOpenAI

        return AsyncOpenAI(**self._client_kwargs)

    def recover_after_error(self, error: BaseException) -> bool:
        _ = error
        try:
            self.client = self._build_client()
            return True
        except Exception:
            return False


def build_openai_compatible_response(
    response: Any,
    *,
    provider_name: str,
    default_model: str,
    reasoning_details_from_message: Callable[[Any], list[dict[str, Any]] | None] | None = None,
) -> LLMResponse:
    """Build a normalized LLMResponse from an OpenAI-compatible chat response."""
    message_result = extract_openai_compatible_message(
        response,
        provider_name=provider_name,
        default_model=default_model,
    )
    if message_result.fallback_response is not None:
        return message_result.fallback_response

    message = message_result.message
    return LLMResponse(
        content=coerce_content(getattr(message, "content", "")),
        model=getattr(response, "model", default_model),
        tool_calls=extract_openai_compatible_tool_calls(message, provider_name=provider_name),
        usage=usage_payload(getattr(response, "usage", None)),
        finish_reason=str(getattr(message_result.choice, "finish_reason", "") or "") or None,
        reasoning_details=(
            reasoning_details_from_message(message)
            if reasoning_details_from_message is not None
            else None
        ),
    )
