"""Offline security tests for the fixed provider HTTP adapters."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from opensprite_backend.models import ErrorCode
from opensprite_backend.providers import (
    ANTHROPIC_MODELS_URL,
    MAX_PROVIDER_RESPONSE_BYTES,
    OPENAI_MODELS_URL,
    ProviderValidationError,
    ProviderValidator,
)

SECRET = "provider-secret-must-not-leak"


def run(coroutine: object) -> object:
    return asyncio.run(coroutine)  # type: ignore[arg-type]


def test_openai_uses_exact_endpoint_and_bearer_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            await ProviderValidator(client).validate("openai", SECRET)

    run(scenario())
    assert len(seen) == 1
    assert str(seen[0].url) == OPENAI_MODELS_URL
    assert seen[0].method == "GET"
    assert seen[0].headers["authorization"] == f"Bearer {SECRET}"
    assert "x-api-key" not in seen[0].headers
    assert seen[0].extensions["timeout"] == {
        "connect": 30.0,
        "read": 30.0,
        "write": 30.0,
        "pool": 30.0,
    }


def test_anthropic_uses_exact_endpoint_and_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [{}]})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            await ProviderValidator(client).validate("anthropic", SECRET)

    run(scenario())
    assert len(seen) == 1
    assert str(seen[0].url) == ANTHROPIC_MODELS_URL
    assert seen[0].headers["x-api-key"] == SECRET
    assert seen[0].headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in seen[0].headers


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ErrorCode.INVALID_CREDENTIALS),
        (403, ErrorCode.INVALID_CREDENTIALS),
        (429, ErrorCode.PROVIDER_RATE_LIMITED),
        (500, ErrorCode.PROVIDER_UNREACHABLE),
        (503, ErrorCode.PROVIDER_UNREACHABLE),
        (400, ErrorCode.PROVIDER_UNREACHABLE),
        (404, ErrorCode.PROVIDER_UNREACHABLE),
    ],
)
def test_non_success_status_mapping(status: int, expected: ErrorCode) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    status,
                    text=f"private:{SECRET}",
                    request=request,
                )
            )
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await ProviderValidator(client).validate("openai", SECRET)
        assert raised.value.code is expected
        assert SECRET not in str(raised.value)
        assert SECRET not in repr(raised.value)

    run(scenario())


@pytest.mark.parametrize(
    "payload",
    [b"not-json", b"[]", b"{}", b'{"data":{}}', b'{"data":null}'],
)
def test_malformed_success_fails_closed_without_body(payload: bytes) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload, request=request)
            )
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await ProviderValidator(client).validate("anthropic", SECRET)
        assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE
        assert payload.decode(errors="ignore") not in str(raised.value)

    run(scenario())


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (httpx.ReadTimeout(SECRET), ErrorCode.PROVIDER_TIMEOUT),
        (httpx.ConnectError(SECRET), ErrorCode.PROVIDER_UNREACHABLE),
        (RuntimeError(SECRET), ErrorCode.PROVIDER_UNREACHABLE),
    ],
)
def test_transport_failures_are_sanitized(
    failure: Exception,
    expected: ErrorCode,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise failure

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await ProviderValidator(client).validate("openai", SECRET)
        assert raised.value.code is expected
        assert raised.value.__context__ is None
        assert raised.value.__cause__ is None
        assert SECRET not in repr(raised.value)

    run(scenario())


def test_redirect_is_not_followed() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302,
            headers={"location": "https://attacker.invalid/steal"},
            request=request,
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await ProviderValidator(client).validate("openai", SECRET)
        assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE

    run(scenario())
    assert calls == 1


def test_success_body_at_limit_is_accepted() -> None:
    payload = b'{"data":[]}'
    payload += b" " * (MAX_PROVIDER_RESPONSE_BYTES - len(payload))

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload, request=request)
            )
        ) as client:
            await ProviderValidator(client).validate("openai", SECRET)

    run(scenario())


def test_oversized_success_body_fails_closed() -> None:
    payload = b'{"data":[]}'
    payload += b" " * (MAX_PROVIDER_RESPONSE_BYTES + 1 - len(payload))

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload, request=request)
            )
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await ProviderValidator(client).validate("anthropic", SECRET)
        assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE
        assert SECRET not in repr(raised.value)

    run(scenario())
