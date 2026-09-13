from uuid import uuid4
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import json

import httpx
import pytest

from opensprite_backend.inference.models import ModelRequest, ModelMessage, ModelTextDelta
from opensprite_backend.inference.native_gateway import NativeModelGateway
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.providers.operation_locks import ProviderOperationLocks


@pytest.mark.anyio
@pytest.mark.parametrize("structured", [False, True])
async def test_custom_tools_use_protocol_not_json_text(structured):
    from opensprite_backend.inference.models import ModelToolDefinition, ModelToolCall

    class Credentials:
        def get(self, key):
            raise AssertionError("no-auth provider must not read credentials")

    arguments = '{"expression":"12345 * 6789"}'
    text = '{"name":"calculator","arguments":' + arguments + '}'

    def handler(request):
        body = json.loads(request.content)
        assert body["tool_choice"] == "auto"
        assert body["tools"][0]["function"]["name"] == "calculator"
        delta = {"tool_calls": [{"index": 0, "id": "call_test", "type": "function",
            "function": {"name": "calculator", "arguments": arguments}}]} if structured else {"content": text}
        payload = {"choices": [{"index": 0, "delta": delta,
            "finish_reason": "tool_calls" if structured else "stop"}]}
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
            content=("data: " + json.dumps(payload) + "\n\ndata: [DONE]\n\n").encode())

    provider_id = str(uuid4())
    endpoint = ProviderEndpointSnapshot(provider_id, 1, "openai_chat_completions", "https://custom.example/v1", "none")
    request = ModelRequest(provider_id=provider_id, model_id="custom", response_mode="default",
        messages=(ModelMessage(role="user", content="calculate"),), provider_endpoint=endpoint,
        tools=(ModelToolDefinition(name="calculator", description="Arithmetic",
            input_schema={"type": "object", "properties": {"expression": {"type": "string"}},
                "required": ["expression"], "additionalProperties": False}),))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        events = [event async for event in NativeModelGateway(Credentials(), client, ProviderOperationLocks()).stream(request)]
    calls = [event for event in events if isinstance(event, ModelToolCall)]
    assert len(calls) == int(structured)
    if structured:
        assert calls[0].arguments == {"expression": "12345 * 6789"}
    else:
        assert any(isinstance(event, ModelTextDelta) and event.text == text for event in events)


@pytest.mark.anyio
async def test_custom_inference_uses_snapshot_without_auth():
    class Credentials:
        def get(self, key):
            raise AssertionError("no-auth provider must not read credentials")
    def handler(request):
        assert str(request.url) == "https://custom.example/v1/chat/completions"
        assert "authorization" not in request.headers
        return httpx.Response(200, headers={"Content-Type":"text/event-stream"}, content=b'data: {"choices":[{"index":0,"delta":{"content":"hello"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
    provider_id = str(uuid4())
    endpoint = ProviderEndpointSnapshot(provider_id, 1, "openai_chat_completions", "https://custom.example/v1", "none")
    request = ModelRequest(provider_id=provider_id, model_id="custom", response_mode="default", messages=(ModelMessage(role="user", content="hi"),), tools=(), provider_endpoint=endpoint)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = NativeModelGateway(Credentials(), client, ProviderOperationLocks())
        events = [event async for event in gateway.stream(request)]
    assert any(isinstance(event, ModelTextDelta) and event.text == "hello" for event in events)


@pytest.mark.anyio
async def test_custom_gateway_over_real_loopback_http():
    """Exercise HTTP serialization and SSE decoding without a remote account."""
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, self.headers.get("Authorization"), json.loads(body)))
            payload = b'data: {"choices":[{"index":0,"delta":{"content":"loopback verified"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    provider_id = str(uuid4())
    class Credentials:
        def get(self, key):
            assert key == f"provider:{provider_id}:bearer"
            return "test-only-token"

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = ProviderEndpointSnapshot(provider_id, 1, "openai_chat_completions",
            f"http://127.0.0.1:{server.server_port}/v1", "bearer")
        request = ModelRequest(provider_id=provider_id, model_id="custom", response_mode="default",
            messages=(ModelMessage(role="user", content="test request"),), tools=(), provider_endpoint=endpoint)
        async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
            gateway = NativeModelGateway(Credentials(), client, ProviderOperationLocks())
            events = [event async for event in gateway.stream(request)]
        assert any(isinstance(event, ModelTextDelta) and event.text == "loopback verified" for event in events)
        assert len(received) == 1
        path, authorization, body = received[0]
        assert path == "/v1/chat/completions"
        assert authorization == "Bearer test-only-token"
        assert body["model"] == "custom" and body["stream"] is True
        assert body["messages"] == [{"role": "user", "content": "test request"}]
        assert "provider" not in body and "plugins" not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
