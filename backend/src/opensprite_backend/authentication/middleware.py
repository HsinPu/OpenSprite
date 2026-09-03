"""Default-deny authentication and response security headers."""

from __future__ import annotations

from collections.abc import Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .service import LocalAuthenticationOperations


SESSION_COOKIE = "__Host-OpenSpriteSession"
PUBLIC_API = frozenset({
    "/api/app-info",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
})
_SECURITY_HEADERS = (
    (b"content-security-policy", b"default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
)


class LocalAuthenticationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        authentication: LocalAuthenticationOperations,
        unauthorized_response: Callable[[], Response],
    ) -> None:
        self._app = app
        self._authentication = authentication
        self._unauthorized_response = unauthorized_response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith("/api/") and scope.get("path") not in PUBLIC_API:
            request = Request(scope)
            token = request.cookies.get(SESSION_COOKIE)
            if await self._authentication.authenticate(token) is None:
                response = self._unauthorized_response()
                await response(scope, receive, send)
                return
            scope.setdefault("state", {})["opensprite_session_token"] = token
        await self._app(scope, receive, send)


class ResponseSecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._app(scope, receive, self._secured(send) if scope["type"] == "http" else send)

    @staticmethod
    def _secured(send: Send) -> Send:
        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                headers.extend(item for item in _SECURITY_HEADERS if item[0] not in existing)
                message = {**message, "headers": headers}
            await send(message)
        return secured
