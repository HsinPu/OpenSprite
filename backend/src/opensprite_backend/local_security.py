"""Deny-by-default HTTP boundary for the loopback desktop runtime."""

from collections.abc import Callable
from dataclasses import dataclass

from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

_LOOPBACK_HOSTNAMES = frozenset({"localhost", "127.0.0.1"})
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True, slots=True)
class _Authority:
    hostname: str
    port: int | None


def _decode_header(value: bytes) -> str | None:
    if len(value) > 128:
        return None
    try:
        decoded = value.decode("ascii")
    except UnicodeDecodeError:
        return None
    if not decoded or any(
        ord(character) <= 0x20 or ord(character) == 0x7F
        for character in decoded
    ):
        return None
    return decoded


def _parse_port(value: str) -> int | None:
    if (
        not value
        or len(value) > 5
        or not value.isascii()
        or not value.isdecimal()
    ):
        return None
    if len(value) > 1 and value.startswith("0"):
        return None
    port = int(value)
    return port if 1 <= port <= 65535 else None


def _parse_authority(value: str) -> _Authority | None:
    if "@" in value or any(character in value for character in "/?#"):
        return None

    if value.startswith("["):
        closing_bracket = value.find("]")
        if closing_bracket < 0 or value[1:closing_bracket].lower() != "::1":
            return None
        hostname = "::1"
        remainder = value[closing_bracket + 1 :]
        if not remainder:
            return _Authority(hostname, None)
        if not remainder.startswith(":") or remainder.count(":") != 1:
            return None
        port = _parse_port(remainder[1:])
        return _Authority(hostname, port) if port is not None else None

    if "[" in value or "]" in value or value.count(":") > 1:
        return None
    hostname, separator, port_text = value.partition(":")
    hostname = hostname.lower()
    if hostname not in _LOOPBACK_HOSTNAMES:
        return None
    if not separator:
        return _Authority(hostname, None)
    port = _parse_port(port_text)
    return _Authority(hostname, port) if port is not None else None


def _parse_origin(value: bytes) -> tuple[str, _Authority] | None:
    decoded = _decode_header(value)
    if decoded is None:
        return None
    separator = decoded.find("://")
    if separator <= 0:
        return None
    scheme = decoded[:separator].lower()
    if scheme not in _DEFAULT_PORTS:
        return None
    authority_text = decoded[separator + 3 :]
    authority = _parse_authority(authority_text)
    if authority is None:
        return None
    return scheme, authority


def _effective_port(scheme: str, authority: _Authority) -> int:
    return authority.port if authority.port is not None else _DEFAULT_PORTS[scheme]


def _is_same_origin(
    *,
    request_scheme: str,
    request_authority: _Authority,
    origin_value: bytes,
) -> bool:
    parsed_origin = _parse_origin(origin_value)
    if parsed_origin is None or request_scheme not in _DEFAULT_PORTS:
        return False
    origin_scheme, origin_authority = parsed_origin
    return (
        origin_scheme == request_scheme
        and origin_authority.hostname == request_authority.hostname
        and _effective_port(origin_scheme, origin_authority)
        == _effective_port(request_scheme, request_authority)
    )


class LocalRequestSecurityMiddleware:
    """Reject requests outside the explicit loopback/same-origin policy."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        rejection_response: Callable[[], Response],
    ) -> None:
        self._app = app
        self._rejection_response = rejection_response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = scope["headers"]
        host_values = [
            value for name, value in headers if name.lower() == b"host"
        ]
        if len(host_values) != 1:
            await self._reject(scope, receive, send)
            return
        decoded_host = _decode_header(host_values[0])
        request_authority = (
            _parse_authority(decoded_host) if decoded_host is not None else None
        )
        if request_authority is None:
            await self._reject(scope, receive, send)
            return

        method = scope["method"].upper()
        if method in _STATE_CHANGING_METHODS:
            origin_values = [
                value for name, value in headers if name.lower() == b"origin"
            ]
            request_scheme = scope.get("scheme", "").lower()
            if len(origin_values) != 1 or not _is_same_origin(
                request_scheme=request_scheme,
                request_authority=request_authority,
                origin_value=origin_values[0] if origin_values else b"",
            ):
                await self._reject(scope, receive, send)
                return

        await self._app(scope, receive, send)

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = self._rejection_response()
        await response(scope, receive, send)
