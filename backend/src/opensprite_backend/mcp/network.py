"""Fail-closed target policy for Streamable HTTP MCP endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from ipaddress import ip_address
import socket
from urllib.parse import SplitResult, urlsplit, urlunsplit


ResolveHost = Callable[[str, int], Awaitable[tuple[str, ...]]]


class McpNetworkPolicyError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class McpNetworkTargetPolicy:
    def __init__(self, resolver: ResolveHost | None = None) -> None:
        self._resolver = resolver or _resolve_host

    async def validate(self, value: str) -> str:
        normalized = normalize_streamable_http_url(value)
        parsed = urlsplit(normalized)
        host = parsed.hostname
        if host is None:
            raise McpNetworkPolicyError("remote_url_blocked")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            literal = ip_address(host)
            addresses = (literal,)
        except ValueError:
            try:
                async with asyncio.timeout(5):
                    resolved = await self._resolver(host, port)
            except (OSError, TimeoutError) as error:
                raise McpNetworkPolicyError("server_unreachable") from error
            if not resolved or len(resolved) > 16:
                raise McpNetworkPolicyError("remote_url_blocked")
            try:
                addresses = tuple(ip_address(item) for item in resolved)
            except ValueError as error:
                raise McpNetworkPolicyError("remote_url_blocked") from error
        if parsed.scheme == "http":
            if not all(address.is_loopback for address in addresses):
                raise McpNetworkPolicyError("remote_url_blocked")
        elif not all(address.is_global for address in addresses):
            raise McpNetworkPolicyError("remote_url_blocked")
        return normalized


def normalize_streamable_http_url(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or any(character.isspace() or ord(character) < 32 for character in value)
        or "\\" in value
    ):
        raise McpNetworkPolicyError("remote_url_blocked")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise McpNetworkPolicyError("remote_url_blocked") from error
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise McpNetworkPolicyError("remote_url_blocked")
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise McpNetworkPolicyError("remote_url_blocked") from error
    if not host or host.endswith(".") or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-.:" for character in host):
        raise McpNetworkPolicyError("remote_url_blocked")
    rendered_host = f"[{host}]" if ":" in host else host
    netloc = rendered_host if port is None else f"{rendered_host}:{port}"
    normalized = SplitResult(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        path=parsed.path or "/",
        query="",
        fragment="",
    )
    return urlunsplit(normalized)


async def _resolve_host(host: str, port: int) -> tuple[str, ...]:
    records = await asyncio.to_thread(
        socket.getaddrinfo,
        host,
        port,
        type=socket.SOCK_STREAM,
    )
    return tuple(sorted({record[4][0] for record in records}))
