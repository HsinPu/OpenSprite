"""Native provider JSON responses retain real tool-result round trips."""
import asyncio
import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest

from opensprite_backend.inference.openai import OpenAIInferenceAdapter
from opensprite_backend.inference.anthropic import AnthropicInferenceAdapter
from opensprite_backend.inference.openrouter import OpenRouterInferenceAdapter
from opensprite_backend.inference.models import ModelRequest, ModelMessage, ModelToolDefinition, ModelToolCall, ModelCompleted, ModelFinishReason
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.tools.builtins.calculator import CalculatorTool
from opensprite_backend.tools.definition import ToolContext


@pytest.mark.parametrize("provider,adapter_type,protocol", [
    ("openai", OpenAIInferenceAdapter, "openai_responses"),
    ("anthropic", AnthropicInferenceAdapter, "anthropic_messages"),
    ("openrouter", OpenRouterInferenceAdapter, "openrouter"),
])
def test_native_non_streaming_tool_roundtrip(provider, adapter_type, protocol):
    async def run():
        bodies = []
        def respond(request):
            body = json.loads(request.content)
            bodies.append(body)
            assert body["stream"] is False
            assert body["tools"]
            second = len(bodies) == 2
            if provider == "openai":
                if second:
                    assert body["input"][-1]["type"] == "function_call_output"
                    assert body["input"][-1]["call_id"] == "calc1"
                output = [{"type": "message", "content": [{"type": "output_text", "text": "42"}]}] if second else [{"type": "function_call", "call_id": "calc1", "name": "calculator", "arguments": '{"expression":"6*7"}'}]
                payload = {"status": "completed", "output": output}
            elif provider == "anthropic":
                if second:
                    assert body["messages"][-1]["content"][0]["tool_use_id"] == "calc1"
                content = [{"type": "text", "text": "42"}] if second else [{"type": "tool_use", "id": "calc1", "name": "calculator", "input": {"expression": "6*7"}}]
                payload = {"type": "message", "role": "assistant", "content": content, "stop_reason": "end_turn" if second else "tool_use"}
            else:
                if second:
                    assert body["messages"][-1]["tool_call_id"] == "calc1"
                message = {"role": "assistant", "content": "42" if second else None}
                if not second:
                    message["tool_calls"] = [{"id": "calc1", "type": "function", "function": {"name": "calculator", "arguments": '{"expression":"6*7"}'}}]
                payload = {"choices": [{"index": 0, "message": message, "finish_reason": "stop" if second else "tool_calls"}]}
            return httpx.Response(200, json=payload)
        endpoint = ProviderEndpointSnapshot(provider, 1, protocol, "https://example.com", "bearer", non_streaming_tools=True)
        request = ModelRequest(provider_id=provider, model_id="test-model", response_mode="default", messages=(ModelMessage("user", "calculate"),), tools=(ModelToolDefinition("calculator", "Calculate", {"type":"object", "properties":{"expression":{"type":"string"}}, "required":["expression"], "additionalProperties":False}),), provider_endpoint=endpoint)
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            adapter = adapter_type(client)
            events = [event async for event in adapter.stream(request, "test-key")]
            calls = [event for event in events if isinstance(event, ModelToolCall)]
            assert len(calls) == 1
            call = calls[0]
            result = await CalculatorTool().invoke(call.arguments, ToolContext(str(uuid4()), str(uuid4()), asyncio.Event()))
            assert "42" in result.content
            followup = replace(request, messages=(*request.messages, ModelMessage("assistant", "", (call,)), ModelMessage("tool", result.content, tool_call_id=call.call_id, tool_name=call.name)))
            final = [event async for event in adapter.stream(followup, "test-key")]
            assert final[-1] == ModelCompleted(ModelFinishReason.FINAL)
            assert len(bodies) == 2
    asyncio.run(run())


@pytest.mark.parametrize("provider,payload", [
    ("openai", {"status":"completed","output":[{"type":"function_call","call_id":"x","name":"calculator","arguments":"not json"}]}),
    ("openai", {"status":"incomplete","incomplete_details":{"reason":"max_output_tokens"},"output":[{"type":"function_call","call_id":"x","name":"calculator","arguments":"{}"}]}),
    ("anthropic", {"type":"message","role":"assistant","stop_reason":"tool_use","content":[]}),
    ("anthropic", {"type":"message","role":"assistant","stop_reason":"max_tokens","content":[{"type":"tool_use","id":"x","name":"calculator","input":{}}]}),
    ("anthropic", {"type":"message","role":"assistant","stop_reason":"tool_use","content":[{"type":"tool_use","name":"calculator","input":{}}]}),
])
def test_invalid_native_completion_does_not_expose_tool_calls(provider, payload):
    from opensprite_backend.inference.openai import _complete_response as openai_complete
    from opensprite_backend.inference.anthropic import _complete_response as anthropic_complete
    from opensprite_backend.inference.gateway import ModelGatewayError
    from opensprite_backend.inference.sse import StreamFormatError
    with pytest.raises((ModelGatewayError, StreamFormatError)):
        (openai_complete if provider == "openai" else anthropic_complete)(payload)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_plain_json_text_does_not_execute(provider):
    from opensprite_backend.inference.openai import _complete_response as openai_complete
    from opensprite_backend.inference.anthropic import _complete_response as anthropic_complete
    text = '{"name":"calculator","arguments":{"expression":"6*7"}}'
    payload = {"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":text}]}]} if provider == "openai" else {"type":"message","role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":text}]}
    events = (openai_complete if provider == "openai" else anthropic_complete)(payload)
    assert not any(isinstance(event, ModelToolCall) for event in events)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("duplicate", [False, True])
def test_native_multiple_calls_preserve_ids_and_reject_duplicates(provider, duplicate):
    from opensprite_backend.inference.openai import _complete_response as openai_complete
    from opensprite_backend.inference.anthropic import _complete_response as anthropic_complete
    from opensprite_backend.inference.gateway import ModelGatewayError
    ids = ["first", "first" if duplicate else "second"]
    if provider == "openai":
        payload = {"status": "completed", "output": [{"type": "function_call", "call_id": identifier, "name": "calculator", "arguments": '{"expression":"6*7"}'} for identifier in ids]}
    else:
        payload = {"type": "message", "role": "assistant", "stop_reason": "tool_use", "content": [{"type": "tool_use", "id": identifier, "name": "calculator", "input": {"expression": "6*7"}} for identifier in ids]}
    complete = openai_complete if provider == "openai" else anthropic_complete
    if duplicate:
        with pytest.raises(ModelGatewayError):
            complete(payload)
    else:
        assert [event.call_id for event in complete(payload) if isinstance(event, ModelToolCall)] == ids
