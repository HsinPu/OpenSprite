"""Adversarial checks for the secured local HTTP boundary."""

from asyncio import run
from datetime import UTC, datetime
import json
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.types import Message, Scope

from opensprite_backend import create_app
from opensprite_backend.models import (
    OpenRouterModel,
    OpenRouterModelListResponse,
    ProviderId,
    ProviderListResponse,
    ProviderStatus,
    ProviderSummary,
)

INVALID_REQUEST = {
    "error": {
        "code": "invalid_request",
        "message": "Request validation failed.",
        "retryable": False,
    }
}


class RecordingConnections:
    def __init__(self) -> None:
        self.list_calls = 0
        self.models_calls = 0
        self.connect_calls = 0
        self.test_calls = 0

    async def list_providers(self) -> ProviderListResponse:
        self.list_calls += 1
        return ProviderListResponse(
            providers=[
                self._summary("openai", False),
                self._summary("anthropic", False),
                self._summary("openrouter", False),
            ]
        )

    async def list_openrouter_models(self) -> OpenRouterModelListResponse:
        self.models_calls += 1
        return OpenRouterModelListResponse(
            models=[OpenRouterModel(id="openai/gpt-4", name="GPT-4", contextWindowTokens=8192, maxOutputTokens=4096)]
        )

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary:
        del api_key
        self.connect_calls += 1
        return self._summary(provider_id, True)

    async def test(self, provider_id: ProviderId) -> ProviderSummary:
        self.test_calls += 1
        return self._summary(provider_id, True)

    async def disconnect(self, provider_id: ProviderId) -> None:
        del provider_id

    @staticmethod
    def _summary(
        provider_id: ProviderId,
        connected: bool,
    ) -> ProviderSummary:
        return ProviderSummary(
            id=provider_id,
            name={
                "openai": "OpenAI",
                "anthropic": "Anthropic",
                "openrouter": "OpenRouter",
            }[provider_id],
            connected=connected,
            status=(
                ProviderStatus.CONNECTED
                if connected
                else ProviderStatus.DISCONNECTED
            ),
            credentialPreview="••••test" if connected else None,
            lastCheckedAt=(
                datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
                if connected
                else None
            ),
        )


def secured_app(connections: RecordingConnections | None = None) -> FastAPI:
    return create_app(
        connections or RecordingConnections(),
        enforce_local_security=True,
    )


def asgi_request(
    app: FastAPI,
    *,
    method: str = "GET",
    scheme: str = "http",
    headers: list[tuple[bytes, bytes]],
    path: str = "/healthz",
    body: bytes = b"",
) -> tuple[int, bytes]:
    sent: list[Message] = []
    request_messages: list[Message] = [
        {"type": "http.request", "body": body, "more_body": False}
    ]
    scope = cast(
        Scope,
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": scheme,
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", 8000),
        },
    )

    async def receive() -> Message:
        if request_messages:
            return request_messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    run(app(scope, receive, send))
    start = next(
        message
        for message in sent
        if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        cast(bytes, message.get("body", b""))
        for message in sent
        if message["type"] == "http.response.body"
    )
    return cast(int, start["status"]), response_body


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost",
        "http://localhost:1",
        "http://127.0.0.1:8765",
        "http://127.0.0.1:65535",
        "https://localhost:443",
    ],
)
def test_safe_get_hosts_need_no_origin(base_url: str) -> None:
    response = TestClient(secured_app(), base_url=base_url).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("base_url", "origin"),
    [
        ("http://localhost", "http://localhost"),
        ("http://localhost:80", "http://localhost"),
        ("http://localhost:8765", "HTTP://LOCALHOST:8765"),
        ("https://127.0.0.1:8443", "https://127.0.0.1:8443"),
    ],
)
def test_mutations_require_canonical_same_origin(
    base_url: str,
    origin: str,
) -> None:
    connections = RecordingConnections()
    response = TestClient(
        secured_app(connections),
        base_url=base_url,
    ).put(
        "/api/providers/openai/connection",
        headers={"origin": origin},
        json={"apiKey": "sk-valid-test"},
    )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert connections.connect_calls == 1


def test_openrouter_model_discovery_requires_same_origin() -> None:
    connections = RecordingConnections()
    client = TestClient(
        secured_app(connections),
        base_url="http://localhost:8765",
    )

    rejected = client.post("/api/providers/openrouter/models")
    accepted = client.post(
        "/api/providers/openrouter/models",
        headers={"origin": "http://localhost:8765"},
    )

    assert rejected.status_code == 400
    assert rejected.json() == INVALID_REQUEST
    assert accepted.status_code == 200
    assert connections.models_calls == 1


def test_ipv6_host_and_origin_are_supported_by_the_asgi_boundary() -> None:
    connections = RecordingConnections()
    get_status, get_body = asgi_request(
        secured_app(connections),
        headers=[(b"host", b"[::1]:8765")],
    )
    put_status, put_body = asgi_request(
        secured_app(connections),
        method="PUT",
        headers=[
            (b"host", b"[::1]:8765"),
            (b"origin", b"http://[::1]:8765"),
            (b"content-type", b"application/json"),
        ],
        path="/api/providers/openai/connection",
        body=b'{"apiKey":"sk-valid-test"}',
    )

    assert get_status == 200
    assert json.loads(get_body) == {"status": "ok"}
    assert put_status == 200
    assert json.loads(put_body)["connected"] is True
    assert connections.connect_calls == 1


@pytest.mark.parametrize(
    "host",
    [
        b"",
        b"evil.example",
        b"localhost.evil",
        b"localhost.",
        b"127.0.0.2",
        b"127.1",
        b"127.000.000.001",
        b"2130706433",
        b"0x7f000001",
        b"user@localhost",
        b"localhost/path",
        b"localhost:0",
        b"localhost:65536",
        b"localhost:08080",
        b"localhost:",
        b"::1",
        b"[0:0:0:0:0:0:0:1]",
        b"[::1%25lo0]",
        b"[::1",
        b"localhost,127.0.0.1",
        b"localhost\x00evil",
        b"localhost evil",
        b"\xfflocalhost",
        b"localhost:" + (b"9" * 129),
    ],
)
def test_malformed_or_non_loopback_host_is_rejected(host: bytes) -> None:
    attacker_value = host.decode("ascii", errors="ignore")
    status, body = asgi_request(secured_app(), headers=[(b"host", host)])

    assert status == 400
    assert json.loads(body) == INVALID_REQUEST
    if attacker_value:
        assert attacker_value not in body.decode("utf-8")


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [(b"host", b"localhost"), (b"host", b"127.0.0.1")],
        [(b"Host", b"localhost"), (b"HOST", b"localhost")],
    ],
)
def test_host_must_appear_exactly_once(
    headers: list[tuple[bytes, bytes]],
) -> None:
    status, body = asgi_request(secured_app(), headers=headers)

    assert status == 400
    assert json.loads(body) == INVALID_REQUEST


def test_rejected_host_does_not_reach_provider_handler() -> None:
    connections = RecordingConnections()
    status, body = asgi_request(
        secured_app(connections),
        headers=[(b"host", b"evil.example")],
        path="/api/providers",
    )

    assert status == 400
    assert json.loads(body) == INVALID_REQUEST
    assert connections.list_calls == 0


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "null",
        "*",
        "http://user@localhost:8000",
        "http://localhost:8000/",
        "http://localhost:8000?query",
        "http://localhost:8000#fragment",
        "https://localhost:8000",
        "http://127.0.0.1:8000",
        "http://local%68ost:8000",
        "http://localhost:8001",
        "http://localhost:08000",
        "http://localhost:8000 http://evil.example",
        "http://localhost:8000,http://evil.example",
        "http://localhost:8000\x00evil",
    ],
)
def test_mutation_rejects_missing_opaque_or_cross_origin_value(
    origin: str | None,
) -> None:
    connections = RecordingConnections()
    headers = {"host": "localhost:8000"}
    if origin is not None:
        headers["origin"] = origin
    status, body = asgi_request(
        secured_app(connections),
        method="PUT",
        headers=[
            (name.encode("ascii"), value.encode("ascii"))
            for name, value in headers.items()
        ],
        path="/api/providers/openai/connection",
        body=b'{"apiKey":"not-processed"}',
    )

    assert status == 400
    assert json.loads(body) == INVALID_REQUEST
    assert connections.connect_calls == 0
    if origin is not None:
        assert origin not in body.decode("utf-8")


def test_origin_must_appear_exactly_once_and_handler_is_not_called() -> None:
    connections = RecordingConnections()
    status, body = asgi_request(
        secured_app(connections),
        method="POST",
        headers=[
            (b"host", b"localhost:8000"),
            (b"origin", b"http://localhost:8000"),
            (b"origin", b"http://localhost:8000"),
        ],
        path="/api/providers/openai/connection/test",
    )

    assert status == 400
    assert json.loads(body) == INVALID_REQUEST
    assert connections.connect_calls == 0
    assert connections.test_calls == 0


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_every_state_changing_method_requires_origin(method: str) -> None:
    status, body = asgi_request(
        secured_app(),
        method=method,
        headers=[(b"host", b"localhost:8000")],
        path="/api/providers/openai/connection",
    )

    assert status == 400
    assert json.loads(body) == INVALID_REQUEST


def test_head_does_not_require_origin() -> None:
    status, _ = asgi_request(
        secured_app(),
        method="HEAD",
        headers=[(b"host", b"localhost:8000")],
    )

    assert status == 405


def test_forwarded_headers_are_ignored() -> None:
    rejected_status, _ = asgi_request(
        secured_app(),
        headers=[
            (b"host", b"evil.example"),
            (b"x-forwarded-host", b"localhost"),
            (b"x-forwarded-proto", b"http"),
        ],
    )
    accepted_status, _ = asgi_request(
        secured_app(),
        headers=[
            (b"host", b"localhost"),
            (b"x-forwarded-host", b"evil.example"),
            (b"x-forwarded-proto", b"https"),
        ],
    )

    assert rejected_status == 400
    assert accepted_status == 200
