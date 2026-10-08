"""Anthropic Messages API streaming adapter."""

from __future__ import annotations

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


ANTHROPIC_MESSAGES_URL: Final = "https://api.anthropic.com/v1/messages"


class AnthropicInferenceAdapter:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._http = NativeHttpAdapter(client, ANTHROPIC_MESSAGES_URL)

    async def stream(
        self,
        request: ModelRequest,
        api_key: str,
    ) -> AsyncIterator[ModelStreamEvent]:
        system, messages = _messages(request.messages)
        body: dict[str, object] = {
            "model": request.model_id,
            "max_tokens": request.max_output_tokens,
            "messages": messages,
            "stream": True,
        }
        if system:
            body["system"] = system
        selected_effort = request_effort(request)
        if selected_effort is not None:
            body["output_config"] = {"effort": selected_effort}


        input_tokens: int | None = None
        output_tokens: int | None = None
        stop_reason: str | None = None
        started = False
        stopped = False
        async for raw in self._http.payloads(
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            body=body,
        ):
            payload = load_json_object(raw)
            event_type = payload.get("type")
            if event_type == "message_start":
                if started:
                    raise invalid_response()
                message = payload.get("message")
                if type(message) is not dict:
                    raise invalid_response()
                input_tokens = _token_value(message.get("usage"), "input_tokens")
                started = True
            elif event_type == "content_block_start":
                block = payload.get("content_block")
                index = payload.get("index")
                if type(block) is not dict or type(index) is not int or index < 0:
                    raise invalid_response()
                block_type = block.get("type")
                if block_type == "text":
                    text = block.get("text")
                    if type(text) is not str:
                        raise invalid_response()
                    if text:
                        yield ModelTextDelta(text)
                elif block_type not in {"thinking", "redacted_thinking"}:
                    raise invalid_response()
            elif event_type == "content_block_delta":
                index = payload.get("index")
                delta = payload.get("delta")
                if type(index) is not int or type(delta) is not dict:
                    raise invalid_response()
                delta_type = delta.get("type")
                if delta_type == "text_delta":
                    text = delta.get("text")
                    if type(text) is not str:
                        raise invalid_response()
                    if text:
                        yield ModelTextDelta(text)
                elif delta_type not in {
                    "thinking_delta",
                    "signature_delta",
                    "citations_delta",
                }:
                    raise invalid_response()
            elif event_type == "content_block_stop":
                index = payload.get("index")
                if type(index) is not int:
                    raise invalid_response()
            elif event_type == "message_delta":
                delta = payload.get("delta")
                if type(delta) is not dict:
                    raise invalid_response()
                reason = delta.get("stop_reason")
                if reason is not None:
                    if type(reason) is not str or stop_reason is not None:
                        raise invalid_response()
                    stop_reason = reason
                output_tokens = _token_value(payload.get("usage"), "output_tokens")
            elif event_type == "message_stop":
                if stopped or not started or stop_reason is None:
                    raise invalid_response()
                stopped = True
                if input_tokens is not None or output_tokens is not None:
                    yield ModelUsage(input_tokens, output_tokens)
                if stop_reason == "end_turn":
                    yield ModelCompleted(ModelFinishReason.FINAL)
                elif stop_reason in {"max_tokens", "model_context_window_exceeded"}:
                    yield ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)
                else:
                    raise invalid_response()
            elif event_type == "ping":
                continue
            else:
                raise invalid_response()
        if not stopped:
            raise invalid_response()


def _messages(messages: tuple[ModelMessage, ...]) -> tuple[str, list[dict[str, object]]]:
    system = "\n\n".join(message.content for message in messages if message.role == "system")
    return system, [{"role": message.role, "content": message.content} for message in messages if message.role != "system"]


def _token_value(value: object, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not dict:
        raise invalid_response()
    token = value.get(name)
    if token is None:
        return None
    if type(token) is not int or token < 0:
        raise invalid_response()
    return token
