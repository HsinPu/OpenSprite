"""Security boundary tests for Streamable HTTP destinations."""

from __future__ import annotations

import asyncio
from functools import wraps

import pytest

from opensprite_backend.mcp.network import (
    McpNetworkPolicyError,
    McpNetworkTargetPolicy,
    normalize_streamable_http_url,
)


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return wrapper


@pytest.mark.parametrize("value", [
    "ftp://example.com/mcp",
    "https://user:secret@example.com/mcp",
    "https://example.com/mcp?token=secret",
    "https://example.com/mcp#fragment",
    "https://example.com\\@127.0.0.1/mcp",
    "https://example.com/mcp\n",
])
def test_normalizer_rejects_credential_and_ambiguous_urls(value: str) -> None:
    with pytest.raises(McpNetworkPolicyError) as captured:
        normalize_streamable_http_url(value)
    assert captured.value.code == "remote_url_blocked"


def test_normalizer_canonicalizes_scheme_host_and_default_path() -> None:
    assert normalize_streamable_http_url("HTTPS://MCP.Example.COM") == "https://mcp.example.com/"
    assert normalize_streamable_http_url("http://[::1]:8000/mcp") == "http://[::1]:8000/mcp"


@async_test
async def test_https_requires_only_public_resolved_addresses() -> None:
    async def mixed(_host: str, _port: int) -> tuple[str, ...]:
        return ("93.184.216.34", "10.0.0.5")

    # Documentation ranges are intentionally not globally routable, so use a
    # known global address for the accepted policy result.
    async def global_address(_host: str, _port: int) -> tuple[str, ...]:
        return ("93.184.216.34",)

    assert await McpNetworkTargetPolicy(global_address).validate("https://mcp.example.com/mcp") == "https://mcp.example.com/mcp"
    with pytest.raises(McpNetworkPolicyError) as captured:
        await McpNetworkTargetPolicy(mixed).validate("https://mcp.example.com/mcp")
    assert captured.value.code == "remote_url_blocked"


@async_test
async def test_plain_http_is_loopback_only() -> None:
    async def local(_host: str, _port: int) -> tuple[str, ...]:
        return ("127.0.0.1", "::1")

    async def lan(_host: str, _port: int) -> tuple[str, ...]:
        return ("192.168.1.10",)

    assert await McpNetworkTargetPolicy(local).validate("http://localhost:8000/mcp") == "http://localhost:8000/mcp"
    with pytest.raises(McpNetworkPolicyError):
        await McpNetworkTargetPolicy(lan).validate("http://mcp.lan:8000/mcp")
    with pytest.raises(McpNetworkPolicyError):
        await McpNetworkTargetPolicy().validate("http://8.8.8.8/mcp")
