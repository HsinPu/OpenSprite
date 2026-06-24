"""Cloud browser provider implementations."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from ..config.defaults import (
    DEFAULT_BROWSER_SESSION_TIMEOUT,
    DEFAULT_BROWSER_USE_BASE_URL,
    DEFAULT_BROWSERBASE_BASE_URL,
    DEFAULT_FIRECRAWL_BROWSER_BASE_URL,
)
from ..utils.url import join_url_path
from .browser_provider_base import BrowserRuntimeError, CloudBrowserProvider, CloudBrowserSession


class BrowserbaseCloudProvider(CloudBrowserProvider):
    backend = "browserbase"
    display_name = "Browserbase"

    def __init__(
        self,
        *,
        api_key: str = "",
        project_id: str = "",
        base_url: str = DEFAULT_BROWSERBASE_BASE_URL,
        proxies: bool = True,
        advanced_stealth: bool = False,
        keep_alive: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(transport=transport)
        self.api_key = _first_text(api_key, os.getenv("BROWSERBASE_API_KEY"))
        self.project_id = _first_text(project_id, os.getenv("BROWSERBASE_PROJECT_ID"))
        self.base_url = _clean_base_url(_first_text(base_url, os.getenv("BROWSERBASE_BASE_URL")), DEFAULT_BROWSERBASE_BASE_URL)
        self.proxies = bool(proxies)
        self.advanced_stealth = bool(advanced_stealth)
        self.keep_alive = bool(keep_alive)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.project_id)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "api_key_configured": bool(self.api_key),
            "project_id": self.project_id,
            "base_url": self.base_url,
        }

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        if not self.is_configured():
            raise BrowserRuntimeError("Browserbase requires browserbase_api_key and browserbase_project_id or BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID.")
        body: dict[str, Any] = {
            "projectId": self.project_id,
            "timeout": max(1, int(session_timeout or DEFAULT_BROWSER_SESSION_TIMEOUT)) * 1000,
        }
        if self.keep_alive:
            body["keepAlive"] = True
        if self.proxies:
            body["proxies"] = True
        if self.advanced_stealth:
            body["browserSettings"] = {"advancedStealth": True}
        response = await self._request(
            "POST",
            join_url_path(self.base_url, "/v1/sessions"),
            headers={"Content-Type": "application/json", "X-BB-API-Key": self.api_key},
            json_body=body,
            timeout=timeout,
            error_prefix="Failed to create Browserbase session",
        )
        payload = _json_object(response, "Browserbase session response")
        provider_session_id = _required_text(payload, "id", "Browserbase session id")
        cdp_url = _required_text(payload, "connectUrl", "Browserbase CDP URL")
        return CloudBrowserSession(
            provider_session_id=provider_session_id,
            cdp_url=cdp_url,
            expires_at=time.monotonic() + max(1, int(session_timeout or DEFAULT_BROWSER_SESSION_TIMEOUT)),
        )

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        if not self.is_configured() or not provider_session_id:
            return False
        try:
            await self._request(
                "POST",
                join_url_path(self.base_url, f"/v1/sessions/{provider_session_id}"),
                headers={"Content-Type": "application/json", "X-BB-API-Key": self.api_key},
                json_body={"projectId": self.project_id, "status": "REQUEST_RELEASE"},
                timeout=timeout,
                error_prefix="Failed to close Browserbase session",
            )
            return True
        except BrowserRuntimeError:
            return False


class BrowserUseCloudProvider(CloudBrowserProvider):
    backend = "browser-use"
    display_name = "Browser Use"

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = DEFAULT_BROWSER_USE_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(transport=transport)
        self.api_key = _first_text(api_key, os.getenv("BROWSER_USE_API_KEY"))
        self.base_url = _clean_base_url(_first_text(base_url, os.getenv("BROWSER_USE_BASE_URL")), DEFAULT_BROWSER_USE_BASE_URL)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "api_key_configured": bool(self.api_key),
            "base_url": self.base_url,
        }

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "X-Browser-Use-API-Key": self.api_key}

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        if not self.is_configured():
            raise BrowserRuntimeError("Browser Use requires browser_use_api_key or BROWSER_USE_API_KEY.")
        timeout_minutes = max(1, (max(1, int(session_timeout or DEFAULT_BROWSER_SESSION_TIMEOUT)) + 59) // 60)
        response = await self._request(
            "POST",
            join_url_path(self.base_url, "/browsers"),
            headers=self._headers(),
            json_body={"timeout": timeout_minutes},
            timeout=timeout,
            error_prefix="Failed to create Browser Use session",
        )
        payload = _json_object(response, "Browser Use session response")
        provider_session_id = _required_text(payload, "id", "Browser Use session id")
        cdp_url = str(payload.get("cdpUrl") or payload.get("connectUrl") or "").strip()
        if not cdp_url:
            raise BrowserRuntimeError("Browser Use session response did not include cdpUrl or connectUrl.")
        return CloudBrowserSession(
            provider_session_id=provider_session_id,
            cdp_url=cdp_url,
            expires_at=time.monotonic() + max(1, int(session_timeout or DEFAULT_BROWSER_SESSION_TIMEOUT)),
        )

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        if not self.is_configured() or not provider_session_id:
            return False
        try:
            await self._request(
                "PATCH",
                join_url_path(self.base_url, f"/browsers/{provider_session_id}"),
                headers=self._headers(),
                json_body={"action": "stop"},
                timeout=timeout,
                error_prefix="Failed to close Browser Use session",
            )
            return True
        except BrowserRuntimeError:
            return False


class FirecrawlCloudProvider(CloudBrowserProvider):
    backend = "firecrawl"
    display_name = "Firecrawl"

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = DEFAULT_FIRECRAWL_BROWSER_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(transport=transport)
        self.api_key = _first_text(api_key, os.getenv("FIRECRAWL_API_KEY"))
        self.base_url = _clean_base_url(_first_text(base_url, os.getenv("FIRECRAWL_API_URL")), DEFAULT_FIRECRAWL_BROWSER_BASE_URL)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "api_key_configured": bool(self.api_key),
            "base_url": self.base_url,
        }

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        if not self.is_configured():
            raise BrowserRuntimeError("Firecrawl browser sessions require firecrawl_api_key or FIRECRAWL_API_KEY.")
        ttl = max(1, int(session_timeout or DEFAULT_BROWSER_SESSION_TIMEOUT))
        response = await self._request(
            "POST",
            join_url_path(self.base_url, "/v2/browser"),
            headers=self._headers(),
            json_body={"ttl": ttl},
            timeout=timeout,
            error_prefix="Failed to create Firecrawl browser session",
        )
        payload = _json_object(response, "Firecrawl browser session response")
        provider_session_id = _required_text(payload, "id", "Firecrawl browser session id")
        cdp_url = _required_text(payload, "cdpUrl", "Firecrawl CDP URL")
        return CloudBrowserSession(
            provider_session_id=provider_session_id,
            cdp_url=cdp_url,
            expires_at=time.monotonic() + ttl,
        )

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        if not self.is_configured() or not provider_session_id:
            return False
        try:
            await self._request(
                "DELETE",
                join_url_path(self.base_url, f"/v2/browser/{provider_session_id}"),
                headers=self._headers(),
                timeout=timeout,
                error_prefix="Failed to close Firecrawl browser session",
            )
            return True
        except BrowserRuntimeError:
            return False


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _clean_base_url(value: str, default: str) -> str:
    return (str(value or "").strip() or default).rstrip("/")


def _json_object(response: httpx.Response, label: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise BrowserRuntimeError(f"{label} was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise BrowserRuntimeError(f"{label} was not a JSON object.")
    return payload


def _required_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise BrowserRuntimeError(f"{label} was missing from provider response.")
    return value
