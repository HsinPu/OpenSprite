"""OpenRouter Chat Completions streaming adapter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Final

import httpx

from .http_stream import NativeHttpAdapter
from .models import (
    ModelCompleted,
    ModelFinishReason,
    ModelMessage,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
    ModelUsage,
)
from .reasoning import request_effort, invalid_response
from .sse import load_json_object


OPENROUTER_CHAT_URL: Final = "https://openrouter.ai/api/v1/chat/completions"


class ChatCompletionsInferenceAdapter:
    """Shared wire protocol; provider-specific request extensions are opt-in."""

    def __init__(self, client: httpx.AsyncClient, endpoint: str, *, openrouter_extensions: bool = False, bearer_auth: bool = True) -> None:
        self._http = NativeHttpAdapter(client, endpoint)
        self._openrouter_extensions = openrouter_extensions
        self._bearer_auth = bearer_auth

    async def stream(
        self,
        request: ModelRequest,
        api_key: str,
    ) -> AsyncIterator[ModelStreamEvent]:
        body: dict[str, object] = {
            "model": request.model_id,
            "messages": _messages(request.messages),
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_completion_tokens": request.max_output_tokens,
        }
        selected_effort = request_effort(request)
        if self._openrouter_extensions and selected_effort is not None:
            body["reasoning"] = {"effort": selected_effort, "exclude": True}

        finish_reason: str | None = None
        done = False
        async for raw in self._http.payloads(
            headers={
                **({"Authorization": f"Bearer {api_key}"} if self._bearer_auth else {}),
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            body=body,
        ):
            if raw == "[DONE]":
                done = True
                break
            payload = load_json_object(raw)
            parsed_usage = _usage(payload.get("usage"))
            choices = payload.get("choices")
            if type(choices) is not list:
                raise invalid_response()
            if not choices:
                if parsed_usage is not None:
                    yield parsed_usage
                continue
            if len(choices) != 1 or type(choices[0]) is not dict:
                raise invalid_response()
            choice = choices[0]
            if choice.get("index") != 0:
                raise invalid_response()
            delta = choice.get("delta")
            if type(delta) is not dict:
                raise invalid_response()
            content = delta.get("content")
            if content is not None:
                if type(content) is not str:
                    raise invalid_response()
                if content:
                    yield ModelTextDelta(content)
            if delta.get("tool_calls") or delta.get("function_call"):
                raise invalid_response()
            current_finish = choice.get("finish_reason")
            if current_finish is not None:
                if type(current_finish) is not str or (
                    finish_reason is not None and finish_reason != current_finish
                ):
                    raise invalid_response()
                finish_reason = current_finish
            if parsed_usage is not None:
                yield parsed_usage

        if not done or finish_reason is None:
            raise invalid_response()
        if finish_reason == "length":
            yield ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)
            return
        if finish_reason != "stop":
            raise invalid_response()
        yield ModelCompleted(ModelFinishReason.FINAL)


class OpenRouterInferenceAdapter(ChatCompletionsInferenceAdapter):
    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__(client, OPENROUTER_CHAT_URL, openrouter_extensions=True)


def _messages(messages: tuple[ModelMessage, ...]) -> list[dict[str, object]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _usage(value: object) -> ModelUsage | None:
    if value is None:
        return None
    if type(value) is not dict:
        raise invalid_response()
    input_tokens = value.get("prompt_tokens")
    output_tokens = value.get("completion_tokens")
    if input_tokens is None and output_tokens is None:
        return None
    return ModelUsage(
        _token(input_tokens),
        _token(output_tokens),
    )


def _token(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise invalid_response()
    return value
