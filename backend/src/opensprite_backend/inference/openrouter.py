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
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)
from .reasoning import effort, invalid_response
from .sse import load_json_arguments, load_json_object


OPENROUTER_CHAT_URL: Final = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(slots=True)
class _ToolFragments:
    call_id: str = ""
    name: str = ""
    arguments: str = ""


class OpenRouterInferenceAdapter:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._http = NativeHttpAdapter(client, OPENROUTER_CHAT_URL)

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
        }
        if request.tools:
            body["tools"] = _tools(request.tools)
            body["tool_choice"] = "auto"
        selected_effort = effort(request.response_mode)
        if selected_effort is not None:
            body["reasoning"] = {
                "effort": selected_effort,
                "exclude": True,
            }

        fragments: dict[int, _ToolFragments] = {}
        finish_reason: str | None = None
        done = False
        async for raw in self._http.payloads(
            headers={
                "Authorization": f"Bearer {api_key}",
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
            tool_deltas = delta.get("tool_calls")
            if tool_deltas is not None:
                if type(tool_deltas) is not list:
                    raise invalid_response()
                for item in tool_deltas:
                    _merge_tool_delta(fragments, item)
            current_finish = choice.get("finish_reason")
            if current_finish is not None:
                if type(current_finish) is not str or finish_reason is not None:
                    raise invalid_response()
                finish_reason = current_finish
            if parsed_usage is not None:
                yield parsed_usage

        if not done or finish_reason is None:
            raise invalid_response()
        if fragments:
            if finish_reason != "tool_calls":
                raise invalid_response()
            expected_indexes = list(range(len(fragments)))
            if sorted(fragments) != expected_indexes:
                raise invalid_response()
            for index in expected_indexes:
                item = fragments[index]
                try:
                    yield ModelToolCall(
                        item.call_id,
                        item.name,
                        load_json_arguments(item.arguments),
                    )
                except ValueError as error:
                    raise invalid_response() from error
            yield ModelCompleted(ModelFinishReason.TOOL_CALLS)
            return
        if finish_reason != "stop":
            raise invalid_response()
        yield ModelCompleted(ModelFinishReason.FINAL)


def _messages(messages: tuple[ModelMessage, ...]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for message in messages:
        if message.role == "tool":
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content,
                }
            )
            continue
        item: dict[str, object] = {
            "role": message.role,
            "content": message.content,
        }
        if message.role == "assistant" and message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": _arguments_json(call.arguments),
                    },
                }
                for call in message.tool_calls
            ]
        result.append(item)
    return result


def _tools(tools: tuple[ModelToolDefinition, ...]) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
                "strict": True,
            },
        }
        for tool in tools
    ]


def _merge_tool_delta(
    fragments: dict[int, _ToolFragments],
    item: object,
) -> None:
    if type(item) is not dict:
        raise invalid_response()
    index = item.get("index")
    if type(index) is not int or index < 0:
        raise invalid_response()
    fragment = fragments.setdefault(index, _ToolFragments())
    call_type = item.get("type")
    if call_type is not None and call_type != "function":
        raise invalid_response()
    call_id = item.get("id")
    if call_id is not None:
        if type(call_id) is not str or (
            fragment.call_id and fragment.call_id != call_id
        ):
            raise invalid_response()
        fragment.call_id = call_id
    function = item.get("function")
    if function is not None:
        if type(function) is not dict:
            raise invalid_response()
        name = function.get("name")
        if name is not None:
            if type(name) is not str or (fragment.name and fragment.name != name):
                raise invalid_response()
            fragment.name = name
        arguments = function.get("arguments")
        if arguments is not None:
            if type(arguments) is not str:
                raise invalid_response()
            fragment.arguments += arguments
            if len(fragment.arguments.encode("utf-8")) > 65536:
                raise invalid_response()


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


def _arguments_json(arguments: dict[str, object]) -> str:
    try:
        return json.dumps(
            arguments,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise invalid_response() from error
