"""No-network contract tests for native Provider inference streams."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from functools import wraps
from pathlib import Path

import httpx
import pytest

from context_test_support import TestCapabilityResolver

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunStatus
from opensprite_backend.conversations.sqlite_repository import (
    SqliteConversationRepository,
)
from opensprite_backend.credentials import CredentialStoreUnavailableError
from opensprite_backend.inference.anthropic import ANTHROPIC_MESSAGES_URL
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import (
    InferenceFailure,
    ModelCompleted,
    ModelFinishReason,
    ModelMessage,
    ModelRequest,
    ModelTextDelta,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)
from opensprite_backend.inference.native_gateway import NativeModelGateway
from opensprite_backend.inference.openai import OPENAI_RESPONSES_URL
from opensprite_backend.inference.openrouter import OPENROUTER_CHAT_URL
from opensprite_backend.inference.sse import MAX_EVENT_BYTES
from opensprite_backend.providers.operation_locks import ProviderOperationLocks
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import ToolRegistry


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class FakeCredentials:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = (
            values
            if values is not None
            else {
                "openai": "openai-secret",
                "anthropic": "anthropic-secret",
                "openrouter": "openrouter-secret",
            }
        )
        self.get_calls: list[str] = []
        self.unavailable = False

    def get(self, provider_id: str) -> str | None:
        self.get_calls.append(provider_id)
        if self.unavailable:
            raise CredentialStoreUnavailableError
        return self.values.get(provider_id)

    def fingerprint(self, provider_id: str) -> str | None:
        del provider_id
        raise AssertionError("inference must not read a fingerprint")

    def set(self, provider_id: str, secret: str) -> None:
        del provider_id, secret
        raise AssertionError("inference must not write credentials")

    def delete(self, provider_id: str) -> None:
        del provider_id
        raise AssertionError("inference must not delete credentials")


def sse(*items: object) -> bytes:
    frames: list[bytes] = []
    for item in items:
        data = item if isinstance(item, str) else json.dumps(item, separators=(",", ":"))
        frames.append(f"data: {data}\n\n".encode())
    return b"".join(frames)


def response(request: httpx.Request, *items: object) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream; charset=utf-8"},
        content=sse(*items),
        request=request,
    )


def request(
    provider_id: str,
    *,
    model_id: str | None = None,
    response_mode: str = "default",
    messages: tuple[ModelMessage, ...] | None = None,
    tools: tuple[ModelToolDefinition, ...] = (),
) -> ModelRequest:
    defaults = {
        "openai": "gpt-5.6",
        "anthropic": "claude-sonnet-4",
        "openrouter": "openrouter/auto",
    }
    return ModelRequest(
        provider_id=provider_id,  # type: ignore[arg-type]
        model_id=model_id or defaults[provider_id],
        response_mode=response_mode,  # type: ignore[arg-type]
        messages=messages
        or (
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="hello"),
        ),
        tools=tools,
    )


async def collect(stream: AsyncIterator[object]) -> list[object]:
    return [event async for event in stream]


@async_test
async def test_openrouter_streams_text_usage_and_final_without_reasoning_leak() -> None:
    captured: list[httpx.Request] = []

    def handler(outbound: httpx.Request) -> httpx.Response:
        captured.append(outbound)
        return response(
            outbound,
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": "你",
                            "reasoning": "must stay hidden",
                            "reasoning_details": [{"type": "reasoning.text", "text": "hidden"}],
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "好"},
                        "finish_reason": "stop",
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": ""},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
            "[DONE]",
        )

    credentials = FakeCredentials()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(credentials, client, ProviderOperationLocks())
        events = await collect(gateway.stream(request("openrouter")))

    assert events == [
        ModelTextDelta("你"),
        ModelTextDelta("好"),
        ModelUsage(input_tokens=4, output_tokens=2),
        ModelCompleted(ModelFinishReason.FINAL),
    ]
    assert credentials.get_calls == ["openrouter"]
    outbound = captured[0]
    assert str(outbound.url) == OPENROUTER_CHAT_URL
    assert outbound.headers["authorization"] == "Bearer openrouter-secret"
    assert "http-referer" not in outbound.headers
    assert "x-title" not in outbound.headers
    body = json.loads(outbound.content)
    assert body == {
        "model": "openrouter/auto",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_completion_tokens": 8192,
    }
    assert b"openrouter-secret" not in outbound.content


@async_test
async def test_openrouter_normalizes_length_finish_as_output_limit() -> None:
    def handler(outbound: httpx.Request) -> httpx.Response:
        return response(
            outbound,
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "partial answer"},
                        "finish_reason": "length",
                    }
                ]
            },
            "[DONE]",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        events = await collect(gateway.stream(request("openrouter")))

    assert events == [
        ModelTextDelta("partial answer"),
        ModelCompleted(ModelFinishReason.OUTPUT_LIMIT),
    ]


@async_test
async def test_openrouter_rejects_conflicting_repeated_finish_reason() -> None:
    def handler(outbound: httpx.Request) -> httpx.Response:
        return response(
            outbound,
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "length"}]},
            "[DONE]",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        with pytest.raises(ModelGatewayError) as captured:
            await collect(gateway.stream(request("openrouter")))

    assert captured.value.failure is InferenceFailure.INVALID_PROVIDER_RESPONSE


@async_test
async def test_openrouter_reassembles_strict_tool_arguments() -> None:
    captured: list[dict[str, object]] = []

    def handler(outbound: httpx.Request) -> httpx.Response:
        captured.append(json.loads(outbound.content))
        return response(
            outbound,
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "lookup_note",
                                        "arguments": "{\"query\":",
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": "\"today\"}"},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
            "[DONE]",
        )

    tool = ModelToolDefinition(
        name="lookup_note",
        description="Look up a note.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        events = await collect(
            gateway.stream(request("openrouter", tools=(tool,)))
        )

    assert events == [
        ModelToolCall("call-1", "lookup_note", {"query": "today"}),
        ModelCompleted(ModelFinishReason.TOOL_CALLS),
    ]
    assert captured[0]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "lookup_note",
                "description": "Look up a note.",
                "parameters": tool.input_schema,
                "strict": True,
            },
        }
    ]
    assert captured[0]["tool_choice"] == "auto"
    assert "provider" not in captured[0]


@async_test
async def test_openrouter_explicit_model_requires_tool_parameters() -> None:
    captured: list[dict[str, object]] = []

    def handler(outbound: httpx.Request) -> httpx.Response:
        captured.append(json.loads(outbound.content))
        return response(
            outbound,
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            "[DONE]",
        )

    tool = ModelToolDefinition(
        name="lookup_note",
        description="Look up a note.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        events = await collect(
            gateway.stream(
                request(
                    "openrouter",
                    model_id="openai/gpt-5.6",
                    tools=(tool,),
                )
            )
        )

    assert events == [ModelCompleted(ModelFinishReason.FINAL)]
    assert captured[0]["provider"] == {"require_parameters": True}


@async_test
async def test_openai_responses_stream_text_tool_calls_usage_and_completion() -> None:
    captured: list[dict[str, object]] = []

    def handler(outbound: httpx.Request) -> httpx.Response:
        captured.append(json.loads(outbound.content))
        return response(
            outbound,
            {"type": "response.output_text.delta", "delta": "Checking "},
            {
                "type": "response.reasoning_summary_text.delta",
                "delta": "must stay hidden",
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "fc-item-1",
                "call_id": "call-1",
                "name": "lookup_note",
                "arguments": "{\"query\":\"today\"}",
            },
            {
                "type": "response.completed",
                "response": {
                    "status": "completed",
                    "output": [],
                    "usage": {"input_tokens": 6, "output_tokens": 3},
                },
            },
        )

    tool = ModelToolDefinition(
        name="lookup_note",
        description="Look up a note.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        events = await collect(
            gateway.stream(request("openai", tools=(tool,)))
        )

    assert events == [
        ModelTextDelta("Checking "),
        ModelToolCall("call-1", "lookup_note", {"query": "today"}),
        ModelUsage(input_tokens=6, output_tokens=3),
        ModelCompleted(ModelFinishReason.TOOL_CALLS),
    ]
    body = captured[0]
    assert body["model"] == "gpt-5.6"
    assert body["stream"] is True
    assert body["store"] is False
    assert body["max_output_tokens"] == 8192
    assert "reasoning" not in body
    assert body["tools"] == [
        {
            "type": "function",
            "name": "lookup_note",
            "description": "Look up a note.",
            "parameters": tool.input_schema,
            "strict": True,
        }
    ]


@async_test
async def test_openai_normalizes_incomplete_max_output_as_output_limit() -> None:
    def handler(outbound: httpx.Request) -> httpx.Response:
        return response(
            outbound,
            {"type": "response.output_text.delta", "delta": "partial answer"},
            {
                "type": "response.incomplete",
                "response": {
                    "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"},
                    "output": [],
                    "usage": {"input_tokens": 6, "output_tokens": 8192},
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        events = await collect(gateway.stream(request("openai")))

    assert events == [
        ModelTextDelta("partial answer"),
        ModelUsage(input_tokens=6, output_tokens=8192),
        ModelCompleted(ModelFinishReason.OUTPUT_LIMIT),
    ]


@async_test
async def test_anthropic_streams_text_tool_input_usage_and_tool_stop() -> None:
    captured: list[httpx.Request] = []

    def handler(outbound: httpx.Request) -> httpx.Response:
        captured.append(outbound)
        return response(
            outbound,
            {
                "type": "message_start",
                "message": {"usage": {"input_tokens": 7}},
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": "查詢中"},
            },
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {
                    "type": "tool_use",
                    "id": "toolu-1",
                    "name": "lookup_note",
                    "input": {},
                },
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": "{\"query\":\"today\"}"},
            },
            {"type": "content_block_stop", "index": 1},
            {
                "type": "content_block_start",
                "index": 2,
                "content_block": {"type": "thinking", "thinking": ""},
            },
            {
                "type": "content_block_delta",
                "index": 2,
                "delta": {"type": "thinking_delta", "thinking": "must stay hidden"},
            },
            {"type": "content_block_stop", "index": 2},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"output_tokens": 4},
            },
            {"type": "message_stop"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        events = await collect(gateway.stream(request("anthropic")))

    assert events == [
        ModelTextDelta("查詢中"),
        ModelToolCall("toolu-1", "lookup_note", {"query": "today"}),
        ModelUsage(input_tokens=7, output_tokens=4),
        ModelCompleted(ModelFinishReason.TOOL_CALLS),
    ]
    outbound = captured[0]
    assert str(outbound.url) == ANTHROPIC_MESSAGES_URL
    assert outbound.headers["x-api-key"] == "anthropic-secret"
    assert outbound.headers["anthropic-version"] == "2023-06-01"
    body = json.loads(outbound.content)
    assert body["system"] == "system"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["max_tokens"] == 8192
    assert "output_config" not in body
    assert "thinking" not in body


@pytest.mark.parametrize("stop_reason", ["max_tokens", "model_context_window_exceeded"])
@async_test
async def test_anthropic_normalizes_output_limits(
    stop_reason: str,
) -> None:
    def handler(outbound: httpx.Request) -> httpx.Response:
        return response(
            outbound,
            {"type": "message_start", "message": {"usage": {"input_tokens": 7}}},
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": "partial answer"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason},
                "usage": {"output_tokens": 8192},
            },
            {"type": "message_stop"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        events = await collect(gateway.stream(request("anthropic")))

    assert events == [
        ModelTextDelta("partial answer"),
        ModelUsage(input_tokens=7, output_tokens=8192),
        ModelCompleted(ModelFinishReason.OUTPUT_LIMIT),
    ]


@pytest.mark.parametrize(
    ("provider_id", "mode", "field", "expected"),
    [
        ("openrouter", "fast", "reasoning", {"effort": "low", "exclude": True}),
        ("openrouter", "balanced", "reasoning", {"effort": "medium", "exclude": True}),
        ("openrouter", "deep", "reasoning", {"effort": "high", "exclude": True}),
        ("openai", "fast", "reasoning", {"effort": "low"}),
        ("openai", "balanced", "reasoning", {"effort": "medium"}),
        ("openai", "deep", "reasoning", {"effort": "high"}),
        ("anthropic", "fast", "output_config", {"effort": "low"}),
        ("anthropic", "balanced", "output_config", {"effort": "medium"}),
        ("anthropic", "deep", "output_config", {"effort": "high"}),
    ],
)
def test_response_modes_map_to_native_fields(
    provider_id: str,
    mode: str,
    field: str,
    expected: dict[str, object],
) -> None:
    captured: list[dict[str, object]] = []

    def handler(outbound: httpx.Request) -> httpx.Response:
        captured.append(json.loads(outbound.content))
        if provider_id == "openrouter":
            return response(
                outbound,
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                "[DONE]",
            )
        if provider_id == "openai":
            return response(
                outbound,
                {
                    "type": "response.completed",
                    "response": {"status": "completed", "output": [], "usage": None},
                },
            )
        return response(
            outbound,
            {"type": "message_start", "message": {"usage": {"input_tokens": 1}}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
            {"type": "message_stop"},
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
            await collect(gateway.stream(request(provider_id, response_mode=mode)))

    asyncio.run(scenario())
    assert captured[0][field] == expected


@async_test
async def test_tool_transcript_serialization_is_native_for_each_provider() -> None:
    call = ModelToolCall("call-1", "lookup_note", {"query": "today"})
    messages = (
        ModelMessage(role="system", content="system"),
        ModelMessage(role="user", content="hello"),
        ModelMessage(role="assistant", content="checking", tool_calls=(call,)),
        ModelMessage(
            role="tool",
            content="three notes",
            tool_call_id="call-1",
            tool_name="lookup_note",
        ),
    )
    captured: dict[str, dict[str, object]] = {}

    def handler(outbound: httpx.Request) -> httpx.Response:
        if str(outbound.url) == OPENROUTER_CHAT_URL:
            provider = "openrouter"
            terminal = (
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                "[DONE]",
            )
        elif str(outbound.url) == OPENAI_RESPONSES_URL:
            provider = "openai"
            terminal = (
                {"type": "response.completed", "response": {"status": "completed", "output": [], "usage": None}},
            )
        else:
            provider = "anthropic"
            terminal = (
                {"type": "message_start", "message": {"usage": {"input_tokens": 1}}},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
                {"type": "message_stop"},
            )
        captured[provider] = json.loads(outbound.content)
        return response(outbound, *terminal)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        for provider_id in ("openrouter", "openai", "anthropic"):
            await collect(gateway.stream(request(provider_id, messages=messages)))

    assert captured["openrouter"]["messages"][-2:] == [
        {
            "role": "assistant",
            "content": "checking",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "lookup_note",
                        "arguments": "{\"query\":\"today\"}",
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "three notes"},
    ]
    assert captured["openai"]["input"][-3:] == [
        {"role": "assistant", "content": "checking"},
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "lookup_note",
            "arguments": "{\"query\":\"today\"}",
        },
        {"type": "function_call_output", "call_id": "call-1", "output": "three notes"},
    ]
    assert captured["anthropic"]["messages"][-2:] == [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "checking"},
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "lookup_note",
                    "input": {"query": "today"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call-1", "content": "three notes"}
            ],
        },
    ]


@pytest.mark.parametrize(
    ("status", "failure"),
    [
        (401, InferenceFailure.INVALID_CREDENTIALS),
        (403, InferenceFailure.INVALID_CREDENTIALS),
        (429, InferenceFailure.PROVIDER_RATE_LIMITED),
        (413, InferenceFailure.CONTEXT_LIMIT_EXCEEDED),
        (500, InferenceFailure.PROVIDER_UNREACHABLE),
        (307, InferenceFailure.PROVIDER_UNREACHABLE),
    ],
)
def test_http_statuses_are_sanitized_and_redirects_are_not_followed(
    status: int,
    failure: InferenceFailure,
) -> None:
    calls = 0

    def handler(outbound: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            status,
            headers={"location": "https://evil.example/secret"},
            request=outbound,
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
            with pytest.raises(ModelGatewayError) as captured:
                await collect(gateway.stream(request("openrouter")))
            assert captured.value.failure is failure

    asyncio.run(scenario())
    assert calls == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"error": {"code": "context_length_exceeded", "message": "too long"}},
        {"error": {"type": "invalid_request_error", "message": "Prompt is too long"}},
        {"error": {"code": 400, "message": "Maximum context length exceeded"}},
    ],
)
def test_bounded_provider_error_body_identifies_context_limit(payload: object) -> None:
    def handler(outbound: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=payload, request=outbound)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
            with pytest.raises(ModelGatewayError) as captured:
                await collect(gateway.stream(request("openrouter")))
            assert captured.value.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED

    asyncio.run(scenario())


def test_unrecognized_or_oversized_bad_request_stays_provider_unreachable() -> None:
    payloads = [
        b'{"error":{"code":"invalid_request","message":"bad model"}}',
        b'{"error":{"message":"Prompt is too long' + (b"x" * 70_000) + b'"}}',
    ]

    async def scenario() -> None:
        for payload in payloads:
            def handler(outbound: httpx.Request) -> httpx.Response:
                return httpx.Response(400, content=payload, request=outbound)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
                with pytest.raises(ModelGatewayError) as captured:
                    await collect(gateway.stream(request("openrouter")))
                assert captured.value.failure is InferenceFailure.PROVIDER_UNREACHABLE

    asyncio.run(scenario())


def test_provider_rejection_logs_status_without_response_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_body = "private-upstream-diagnostic"

    def handler(outbound: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": secret_body}},
            request=outbound,
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
            with pytest.raises(ModelGatewayError):
                await collect(gateway.stream(request("openrouter")))

    with caplog.at_level(logging.WARNING, logger="opensprite.inference.http"):
        asyncio.run(scenario())

    messages = [record.getMessage() for record in caplog.records]
    assert "provider request rejected status=400" in messages
    assert all(secret_body not in message for message in messages)


@async_test
async def test_missing_or_unavailable_credential_fails_before_network() -> None:
    calls = 0

    def handler(outbound: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(outbound, "[DONE]")

    credentials = FakeCredentials({})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(credentials, client, ProviderOperationLocks())
        with pytest.raises(ModelGatewayError) as missing:
            await collect(gateway.stream(request("openrouter")))
        credentials.unavailable = True
        with pytest.raises(ModelGatewayError) as unavailable:
            await collect(gateway.stream(request("openrouter")))

    assert missing.value.failure is InferenceFailure.PROVIDER_NOT_CONNECTED
    assert unavailable.value.failure is InferenceFailure.CREDENTIAL_STORE_UNAVAILABLE
    assert calls == 0


@async_test
async def test_gateway_uses_shared_provider_lock_for_entire_stream() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handler(outbound: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        return response(
            outbound,
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            "[DONE]",
        )

    locks = ProviderOperationLocks()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, locks)
        task = asyncio.create_task(collect(gateway.stream(request("openrouter"))))
        await asyncio.wait_for(entered.wait(), timeout=1)
        second_entered = False

        async def second() -> None:
            nonlocal second_entered
            async with locks.hold("openrouter"):
                second_entered = True

        blocked = asyncio.create_task(second())
        await asyncio.sleep(0)
        assert second_entered is False
        release.set()
        await asyncio.wait_for(task, timeout=1)
        await asyncio.wait_for(blocked, timeout=1)
        assert second_entered is True


@async_test
async def test_malformed_stream_and_duplicate_tool_json_fail_closed() -> None:
    responses = [
        httpx.Response(200, content=b"not sse"),
        httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse(
                {
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "lookup_note",
                                            "arguments": "{\"query\":\"one\",\"query\":\"two\"}",
                                        },
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                },
                "[DONE]",
            ),
        ),
    ]

    def handler(outbound: httpx.Request) -> httpx.Response:
        item = responses.pop(0)
        item.request = outbound
        return item

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        for _ in range(2):
            with pytest.raises(ModelGatewayError) as captured:
                await collect(gateway.stream(request("openrouter")))
            assert captured.value.failure is InferenceFailure.INVALID_PROVIDER_RESPONSE


@async_test
async def test_transport_timeout_and_oversized_sse_event_are_bounded() -> None:
    responses: list[object] = [
        httpx.ReadTimeout("private timeout detail"),
        httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b"data: " + (b"x" * (MAX_EVENT_BYTES + 1)) + b"\n\n",
        ),
    ]

    def handler(outbound: httpx.Request) -> httpx.Response:
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, httpx.Response)
        item.request = outbound
        return item

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        with pytest.raises(ModelGatewayError) as timeout:
            await collect(gateway.stream(request("openrouter")))
        with pytest.raises(ModelGatewayError) as oversized:
            await collect(gateway.stream(request("openrouter")))

    assert timeout.value.failure is InferenceFailure.PROVIDER_TIMEOUT
    assert oversized.value.failure is InferenceFailure.INVALID_PROVIDER_RESPONSE
    assert "private timeout detail" not in str(timeout.value)


@async_test
async def test_openai_non_reasoning_model_rejects_explicit_response_mode() -> None:
    calls = 0

    def handler(outbound: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(outbound)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(FakeCredentials(), client, ProviderOperationLocks())
        with pytest.raises(ModelGatewayError) as captured:
            await collect(
                gateway.stream(
                    request("openai", model_id="gpt-4.1", response_mode="deep")
                )
            )

    assert captured.value.failure is InferenceFailure.INVALID_PROVIDER_RESPONSE
    assert calls == 0


@async_test
async def test_native_gateway_to_agent_persists_text_not_secret_or_reasoning(
    tmp_path: Path,
) -> None:
    def handler(outbound: httpx.Request) -> httpx.Response:
        return response(
            outbound,
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": "安全回覆",
                            "reasoning": "private-chain-of-thought",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
            "[DONE]",
        )

    repository = SqliteConversationRepository(
        build_app_paths(tmp_path / ".opensprite").database_file
    )
    accepted = repository.start_run(
        conversation_id=None,
        client_request_id="60ec4506-8fcf-4393-86c4-8583d24f83a7",
        message="hello",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    )
    credentials = FakeCredentials()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        loop = AgentLoop(
            repository=repository,
            gateway=NativeModelGateway(
                credentials,
                client,
                ProviderOperationLocks(),
            ),
            tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
            capability_resolver=TestCapabilityResolver(),
        )
        result = await loop.execute(accepted.run.id, asyncio.Event())

    assert result.status is RunStatus.COMPLETED
    assert result.partial_text == "安全回覆"
    persisted = repository.database_file.read_bytes()
    assert b"openrouter-secret" not in persisted
    assert b"private-chain-of-thought" not in persisted
