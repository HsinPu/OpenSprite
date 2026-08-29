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
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)
from .reasoning import effort, invalid_response
from .sse import load_json_arguments, load_json_object


ANTHROPIC_MESSAGES_URL: Final = "https://api.anthropic.com/v1/messages"


@dataclass(slots=True)
class _ToolBlock:
    call_id: str
    name: str
    initial_input: dict[str, object]
    partial_json: str = ""


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
        if request.tools:
            body["tools"] = _tools(request.tools)
            body["tool_choice"] = {"type": "auto"}
        selected_effort = effort(request.response_mode)
        if selected_effort is not None:
            body["output_config"] = {"effort": selected_effort}

        tools: dict[int, _ToolBlock] = {}
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
                elif block_type == "tool_use":
                    call_id = block.get("id")
                    name = block.get("name")
                    initial = block.get("input")
                    if (
                        type(call_id) is not str
                        or type(name) is not str
                        or type(initial) is not dict
                        or index in tools
                    ):
                        raise invalid_response()
                    tools[index] = _ToolBlock(call_id, name, initial)
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
                elif delta_type == "input_json_delta":
                    partial = delta.get("partial_json")
                    if type(partial) is not str or index not in tools:
                        raise invalid_response()
                    tools[index].partial_json += partial
                    if len(tools[index].partial_json.encode("utf-8")) > 65536:
                        raise invalid_response()
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
                block = tools.pop(index, None)
                if block is not None:
                    arguments = (
                        load_json_arguments(block.partial_json)
                        if block.partial_json
                        else block.initial_input
                    )
                    try:
                        yield ModelToolCall(block.call_id, block.name, arguments)
                    except ValueError as error:
                        raise invalid_response() from error
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
                if stopped or not started or tools or stop_reason is None:
                    raise invalid_response()
                stopped = True
                if input_tokens is not None or output_tokens is not None:
                    yield ModelUsage(input_tokens, output_tokens)
                if stop_reason == "tool_use":
                    yield ModelCompleted(ModelFinishReason.TOOL_CALLS)
                elif stop_reason == "end_turn":
                    yield ModelCompleted(ModelFinishReason.FINAL)
                else:
                    raise invalid_response()
            elif event_type == "ping":
                continue
            else:
                raise invalid_response()
        if not stopped:
            raise invalid_response()


def _messages(
    messages: tuple[ModelMessage, ...],
) -> tuple[str, list[dict[str, object]]]:
    system_parts: list[str] = []
    result: list[dict[str, object]] = []
    pending_tool_results: list[dict[str, object]] = []

    def flush_tool_results() -> None:
        if pending_tool_results:
            result.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
        elif message.role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
            )
        elif message.role == "assistant" and message.tool_calls:
            flush_tool_results()
            content: list[dict[str, object]] = []
            if message.content:
                content.append({"type": "text", "text": message.content})
            content.extend(
                {
                    "type": "tool_use",
                    "id": call.call_id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
            result.append({"role": "assistant", "content": content})
        else:
            flush_tool_results()
            result.append({"role": message.role, "content": message.content})
    flush_tool_results()
    return "\n\n".join(system_parts), result


def _tools(tools: tuple[ModelToolDefinition, ...]) -> list[dict[str, object]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "strict": True,
        }
        for tool in tools
    ]


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
