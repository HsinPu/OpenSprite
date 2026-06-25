"""Base types shared by cloud browser providers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config.defaults import DEFAULT_BROWSER_SESSION_TIMEOUT


class BrowserRuntimeError(RuntimeError):
    """Raised when browser automation cannot run."""


@dataclass
class CloudBrowserSession:
    provider_session_id: str
    cdp_url: str
    expires_at: float


class CloudBrowserProvider:
    """Creates browser CDP sessions for cloud browser backends."""

    backend = ""
    display_name = "Cloud browser"
    auth_header_name = ""
    auth_header_prefix = ""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    def is_configured(self) -> bool:
        return bool(getattr(self, "api_key", ""))

    def status(self) -> dict[str, Any]:
        return self.api_key_status()

    def api_key_status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "api_key_configured": bool(getattr(self, "api_key", "")),
            "base_url": getattr(self, "base_url", ""),
        }

    def session_timeout_seconds(self, session_timeout: int) -> int:
        return max(1, int(session_timeout or DEFAULT_BROWSER_SESSION_TIMEOUT))

    def json_auth_headers(self, header_name: str, header_value: str) -> dict[str, str]:
        return {"Content-Type": "application/json", header_name: header_value}

    def json_api_key_headers(self) -> dict[str, str]:
        return self.json_auth_headers(
            self.auth_header_name,
            f"{self.auth_header_prefix}{getattr(self, 'api_key', '')}",
        )

    def cloud_session(self, provider_session_id: str, cdp_url: str, ttl: int) -> CloudBrowserSession:
        return CloudBrowserSession(
            provider_session_id=provider_session_id,
            cdp_url=cdp_url,
            expires_at=time.monotonic() + ttl,
        )

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        raise NotImplementedError

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        return False

    async def _close_with_request(self, provider_session_id: str, method: str, url: str, **request_kwargs: Any) -> bool:
        if not self.is_configured() or not provider_session_id:
            return False
        try:
            await self._request(method, url, **request_kwargs)
            return True
        except BrowserRuntimeError:
            return False

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any] | None = None,
        timeout: int = 30,
        error_prefix: str,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=max(1, int(timeout or 30)),
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = await client.request(method, url, headers=headers, json=json_body)
        except httpx.HTTPError as exc:
            raise BrowserRuntimeError(f"{error_prefix}: {exc}") from exc
        if response.status_code >= 400:
            raise BrowserRuntimeError(f"{error_prefix}: HTTP {response.status_code} {response.text[:500]}")
        return response
