"""Base types shared by cloud browser providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


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

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    def is_configured(self) -> bool:
        return False

    def status(self) -> dict[str, Any]:
        return {"configured": self.is_configured()}

    def api_key_status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "api_key_configured": bool(getattr(self, "api_key", "")),
            "base_url": getattr(self, "base_url", ""),
        }

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        raise NotImplementedError

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
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
