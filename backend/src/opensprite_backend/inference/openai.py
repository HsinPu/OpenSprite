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
    ModelUsage,
)
from .reasoning import invalid_response, request_effort
from .sse import load_json_object


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
        selected_effort = request_effort(request)
        if selected_effort is not None:
            body["reasoning"] = {"effort": selected_effort}


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
            elif event_type in {"response.output_item.added", "response.output_item.done"}:
                item = payload.get("item")
                if type(item) is not dict:
                    raise invalid_response()
                if item.get("type") not in {"message", "reasoning"}:
                    raise invalid_response()
            elif event_type == "response.completed":
                if terminal:
                    raise invalid_response()
                response = payload.get("response")
                if type(response) is not dict or response.get("status") != "completed":
                    raise invalid_response()
                _validate_output(response.get("output"))
                usage = _usage(response.get("usage"))
                if usage is not None:
                    yield usage
                terminal = True
                yield ModelCompleted(
                    ModelFinishReason.FINAL
                )
            elif event_type == "response.incomplete":
                if terminal:
                    raise invalid_response()
                response = payload.get("response")
                if type(response) is not dict or response.get("status") != "incomplete":
                    raise invalid_response()
                details = response.get("incomplete_details")
                if (
                    type(details) is not dict
                    or details.get("reason") not in {"max_tokens", "max_output_tokens"}
                ):
                    raise invalid_response()
                _validate_output(response.get("output"))
                usage = _usage(response.get("usage"))
                if usage is not None:
                    yield usage
                terminal = True
                yield ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)
            elif event_type in {
                "response.created",
                "response.in_progress",
                "response.queued",
                "response.content_part.added",
                "response.content_part.done",
                "response.output_text.done",
                "response.refusal.done",
            } or event_type.startswith("response.reasoning_"):
                continue
            else:
                raise invalid_response()
        if not terminal:
            raise invalid_response()


def _input(messages: tuple[ModelMessage, ...]) -> list[dict[str, object]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _validate_output(output: object) -> None:
    if type(output) is not list:
        raise invalid_response()
    if any(type(item) is not dict or item.get("type") not in {"message", "reasoning"} for item in output):
        raise invalid_response()


def _usage(value: object) -> ModelUsage | None:
    if value is None:
        return None
    if type(value) is not dict:
        raise invalid_response()
    return ModelUsage(
        _token(value.get("input_tokens")),
        _token(value.get("output_tokens")),
    )


def _token(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise invalid_response()
    return value
