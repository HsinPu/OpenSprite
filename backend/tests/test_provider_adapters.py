"""Offline security tests for the fixed provider HTTP adapters."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from opensprite_backend.models import ErrorCode
from opensprite_backend.providers import (
    ANTHROPIC_MODELS_URL,
    MAX_OPENROUTER_MODELS,
    MAX_OPENROUTER_MODELS_RESPONSE_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES,
    OPENAI_MODELS_URL,
    OPENROUTER_MODELS_URL,
    OpenRouterModelDiscovery,
    ProviderValidationError,
    ProviderValidator,
)
from opensprite_backend.providers.adapters import OPENROUTER_KEY_URL

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


def test_openrouter_uses_exact_key_endpoint_and_bearer_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": {"label": "OpenSprite"}})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            await ProviderValidator(client).validate("openrouter", SECRET)

    run(scenario())
    assert len(seen) == 1
    assert str(seen[0].url) == OPENROUTER_KEY_URL
    assert seen[0].method == "GET"
    assert seen[0].headers["authorization"] == f"Bearer {SECRET}"
    assert "x-api-key" not in seen[0].headers
    assert "http-referer" not in seen[0].headers
    assert "x-title" not in seen[0].headers
    assert seen[0].extensions["timeout"] == {
        "connect": 30.0,
        "read": 30.0,
        "write": 30.0,
        "pool": 30.0,
    }


def test_openrouter_model_discovery_uses_exact_endpoint_and_bearer_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "openai/gpt-4",
                        "name": "GPT-4",
                        "architecture": {
                            "input_modalities": ["text"],
                            "output_modalities": ["text"],
                        },
                    }
                ]
            },
            request=request,
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            result = await OpenRouterModelDiscovery(client).list_models(SECRET)
        assert [(model.id, model.name) for model in result.models] == [
            ("openai/gpt-4", "GPT-4")
        ]

    run(scenario())
    assert len(seen) == 1
    assert str(seen[0].url) == OPENROUTER_MODELS_URL
    assert seen[0].method == "GET"
    assert seen[0].headers["authorization"] == f"Bearer {SECRET}"
    assert "x-api-key" not in seen[0].headers
    assert "http-referer" not in seen[0].headers
    assert "x-title" not in seen[0].headers
    assert seen[0].extensions["timeout"] == {
        "connect": 30.0,
        "read": 30.0,
        "write": 30.0,
        "pool": 30.0,
    }


def test_openrouter_model_discovery_skips_invalid_records_deduplicates_and_sorts() -> None:
    payload = {
        "data": [
            {"id": "skip/not-text", "name": "Skip", "architecture": {"input_modalities": ["image"], "output_modalities": ["text"]}},
            {"id": "z/model", "name": "alpha", "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}},
            {"id": "a/model", "name": "Alpha", "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}},
            {"id": "z/model", "name": "Changed duplicate", "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}},
            {"id": "missing/architecture", "name": "Skip"},
        ]
    }

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload, request=request)
            )
        ) as client:
            result = await OpenRouterModelDiscovery(client).list_models(SECRET)
        assert [(model.id, model.name) for model in result.models] == [
            ("a/model", "Alpha"),
            ("z/model", "alpha"),
        ]

    run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"data":{}}',
        b'{"data":[]}',
        b'{"data":[{"id":"skip","name":"Skip"}]}',
    ],
)
def test_openrouter_model_discovery_rejects_malformed_or_empty_usable_results(
    payload: bytes,
) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload, request=request)
            )
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await OpenRouterModelDiscovery(client).list_models(SECRET)
        assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE
        assert SECRET not in repr(raised.value)

    run(scenario())


@pytest.mark.parametrize(
    "count",
    [MAX_OPENROUTER_MODELS, MAX_OPENROUTER_MODELS + 1],
    ids=["maximum-accepted", "one-over-maximum-rejected"],
)
def test_openrouter_model_discovery_enforces_model_count_limit(count: int) -> None:
    data = [
        {
            "id": f"provider/model-{index}",
            "name": f"Model {index:04d}",
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
        }
        for index in range(count)
    ]

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"data": data}, request=request)
            )
        ) as client:
            discovery = OpenRouterModelDiscovery(client)
            if count == MAX_OPENROUTER_MODELS:
                result = await discovery.list_models(SECRET)
                assert len(result.models) == MAX_OPENROUTER_MODELS
            else:
                with pytest.raises(ProviderValidationError) as raised:
                    await discovery.list_models(SECRET)
                assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE

    run(scenario())


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ErrorCode.INVALID_CREDENTIALS),
        (403, ErrorCode.INVALID_CREDENTIALS),
        (429, ErrorCode.PROVIDER_RATE_LIMITED),
        (404, ErrorCode.PROVIDER_UNREACHABLE),
        (500, ErrorCode.PROVIDER_UNREACHABLE),
        (503, ErrorCode.PROVIDER_UNREACHABLE),
    ],
)
def test_openrouter_model_discovery_maps_upstream_statuses(
    status: int,
    expected: ErrorCode,
) -> None:
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
                await OpenRouterModelDiscovery(client).list_models(SECRET)
        assert raised.value.code is expected
        assert SECRET not in repr(raised.value)

    run(scenario())


def test_openrouter_model_discovery_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise httpx.ReadTimeout(SECRET)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await OpenRouterModelDiscovery(client).list_models(SECRET)
        assert raised.value.code is ErrorCode.PROVIDER_TIMEOUT
        assert SECRET not in repr(raised.value)

    run(scenario())


@pytest.mark.parametrize("extra_bytes", [0, 1])
def test_openrouter_model_discovery_enforces_exact_response_limit(
    extra_bytes: int,
) -> None:
    payload = (
        b'{"data":[{"id":"a","name":"A","architecture":'
        b'{"input_modalities":["text"],"output_modalities":["text"]}}]}'
    )
    payload += b" " * (
        MAX_OPENROUTER_MODELS_RESPONSE_BYTES + extra_bytes - len(payload)
    )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload, request=request)
            )
        ) as client:
            discovery = OpenRouterModelDiscovery(client)
            if extra_bytes == 0:
                result = await discovery.list_models(SECRET)
                assert result.models[0].id == "a"
            else:
                with pytest.raises(ProviderValidationError) as raised:
                    await discovery.list_models(SECRET)
                assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE

    run(scenario())


def test_openrouter_model_discovery_does_not_follow_redirects() -> None:
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
                await OpenRouterModelDiscovery(client).list_models(SECRET)
        assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE

    run(scenario())
    assert calls == 1


@pytest.mark.parametrize("payload", [b"not-json", b'{"data": []}', b'{"data": null}'])
def test_openrouter_requires_object_data_response(payload: bytes) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload, request=request)
            )
        ) as client:
            with pytest.raises(ProviderValidationError) as raised:
                await ProviderValidator(client).validate("openrouter", SECRET)
        assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE
        assert SECRET not in repr(raised.value)

    run(scenario())


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ErrorCode.INVALID_CREDENTIALS),
        (403, ErrorCode.INVALID_CREDENTIALS),
        (429, ErrorCode.PROVIDER_RATE_LIMITED),
        (500, ErrorCode.PROVIDER_UNREACHABLE),
    ],
)
def test_openrouter_non_success_status_mapping(
    status: int,
    expected: ErrorCode,
) -> None:
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
                await ProviderValidator(client).validate("openrouter", SECRET)
        assert raised.value.code is expected
        assert SECRET not in repr(raised.value)

    run(scenario())


@pytest.mark.parametrize("extra_bytes", [0, 1])
def test_openrouter_success_body_limit(extra_bytes: int) -> None:
    payload = b'{"data":{}}'
    payload += b" " * (
        MAX_PROVIDER_RESPONSE_BYTES + extra_bytes - len(payload)
    )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=payload, request=request)
            )
        ) as client:
            if extra_bytes == 0:
                await ProviderValidator(client).validate("openrouter", SECRET)
            else:
                with pytest.raises(ProviderValidationError) as raised:
                    await ProviderValidator(client).validate("openrouter", SECRET)
                assert raised.value.code is ErrorCode.PROVIDER_UNREACHABLE

    run(scenario())


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
