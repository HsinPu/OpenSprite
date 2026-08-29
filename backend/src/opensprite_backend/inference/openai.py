"""OpenAI Responses API streaming adapter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
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
from .reasoning import invalid_response, openai_effort
from .sse import load_json_arguments, load_json_object


OPENAI_RESPONSES_URL: Final = "https://api.openai.com/v1/responses"


class OpenAIInferenceAdapter:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._http = NativeHttpAdapter(client, OPENAI_RESPONSES_URL)

    async def stream(
        self,
        request: ModelRequest,
        api_key: str,
    ) -> AsyncIterator[ModelStreamEvent]:
        body: dict[str, object] = {
            "model": request.model_id,
            "input": _input(request.messages),
            "stream": True,
            "store": False,
            "max_output_tokens": request.max_output_tokens,
        }
        if request.tools:
            body["tools"] = _tools(request.tools)
            body["tool_choice"] = "auto"
        selected_effort = openai_effort(
            request.model_id,
            request.response_mode,
        )
        if selected_effort is not None:
            body["reasoning"] = {"effort": selected_effort}

        call_items: dict[str, tuple[str, str]] = {}
        calls: list[ModelToolCall] = []
        call_ids: set[str] = set()
        terminal = False
        async for raw in self._http.payloads(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            body=body,
        ):
            if raw == "[DONE]":
                if not terminal:
                    raise invalid_response()
                continue
            payload = load_json_object(raw)
            event_type = payload.get("type")
            if type(event_type) is not str:
                raise invalid_response()
            if event_type in {
                "response.output_text.delta",
                "response.refusal.delta",
            }:
                delta = payload.get("delta")
                if type(delta) is not str:
                    raise invalid_response()
                if delta:
                    yield ModelTextDelta(delta)
            elif event_type == "response.output_item.added":
                item = payload.get("item")
                if type(item) is not dict:
                    raise invalid_response()
                if item.get("type") == "function_call":
                    item_id = item.get("id")
                    call_id = item.get("call_id")
                    name = item.get("name")
                    if not all(
                        type(value) is str and value
                        for value in (item_id, call_id, name)
                    ):
                        raise invalid_response()
                    call_items[item_id] = (call_id, name)
            elif event_type == "response.function_call_arguments.done":
                item_id = payload.get("item_id")
                call_id = payload.get("call_id")
                name = payload.get("name")
                arguments = payload.get("arguments")
                if type(item_id) is not str or type(arguments) is not str:
                    raise invalid_response()
                known = call_items.get(item_id)
                if call_id is None and known is not None:
                    call_id = known[0]
                if name is None and known is not None:
                    name = known[1]
                if (
                    type(call_id) is not str
                    or type(name) is not str
                    or call_id in call_ids
                ):
                    raise invalid_response()
                try:
                    call = ModelToolCall(
                        call_id,
                        name,
                        load_json_arguments(arguments),
                    )
                except ValueError as error:
                    raise invalid_response() from error
                call_ids.add(call_id)
                calls.append(call)
                yield call
            elif event_type == "response.completed":
                if terminal:
                    raise invalid_response()
                response = payload.get("response")
                if type(response) is not dict or response.get("status") != "completed":
                    raise invalid_response()
                for call in _completed_calls(response.get("output"), call_ids):
                    call_ids.add(call.call_id)
                    calls.append(call)
                    yield call
                usage = _usage(response.get("usage"))
                if usage is not None:
                    yield usage
                terminal = True
                yield ModelCompleted(
                    ModelFinishReason.TOOL_CALLS
                    if calls
                    else ModelFinishReason.FINAL
                )
            elif event_type in {
                "response.created",
                "response.in_progress",
                "response.queued",
                "response.output_item.done",
                "response.content_part.added",
                "response.content_part.done",
                "response.output_text.done",
                "response.refusal.done",
                "response.function_call_arguments.delta",
            } or event_type.startswith("response.reasoning_"):
                continue
            else:
                raise invalid_response()
        if not terminal:
            raise invalid_response()


def _input(messages: tuple[ModelMessage, ...]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for message in messages:
        if message.role == "tool":
            result.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": message.content,
                }
            )
            continue
        if message.content:
            result.append({"role": message.role, "content": message.content})
        if message.role == "assistant":
            result.extend(
                {
                    "type": "function_call",
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": _arguments_json(call.arguments),
                }
                for call in message.tool_calls
            )
    return result


def _tools(tools: tuple[ModelToolDefinition, ...]) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
            "strict": True,
        }
        for tool in tools
    ]


def _usage(value: object) -> ModelUsage | None:
    if value is None:
        return None
    if type(value) is not dict:
        raise invalid_response()
    return ModelUsage(
        _token(value.get("input_tokens")),
        _token(value.get("output_tokens")),
    )


def _completed_calls(
    output: object,
    seen: set[str],
) -> list[ModelToolCall]:
    if type(output) is not list:
        raise invalid_response()
    calls: list[ModelToolCall] = []
    for item in output:
        if type(item) is not dict or item.get("type") != "function_call":
            continue
        call_id = item.get("call_id")
        name = item.get("name")
        arguments = item.get("arguments")
        if call_id in seen:
            continue
        if (
            type(call_id) is not str
            or type(name) is not str
            or type(arguments) is not str
        ):
            raise invalid_response()
        try:
            calls.append(
                ModelToolCall(call_id, name, load_json_arguments(arguments))
            )
        except ValueError as error:
            raise invalid_response() from error
    return calls


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
