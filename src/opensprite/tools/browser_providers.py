"""Cloud browser provider implementations."""

from __future__ import annotations

from typing import Any

import httpx

from ..config.defaults import (
    DEFAULT_BROWSER_USE_BASE_URL,
    DEFAULT_BROWSERBASE_BASE_URL,
    DEFAULT_FIRECRAWL_BROWSER_BASE_URL,
)
from ..utils.url import join_url_path
from .browser_provider_base import BrowserRuntimeError, CloudBrowserProvider, CloudBrowserSession


class BrowserbaseCloudProvider(CloudBrowserProvider):
    backend = "browserbase"
    display_name = "Browserbase"
    auth_header_name = "X-BB-API-Key"
    api_key_env_var = "BROWSERBASE_API_KEY"
    project_id_env_var = "BROWSERBASE_PROJECT_ID"
    base_url_env_var = "BROWSERBASE_BASE_URL"
    default_base_url = DEFAULT_BROWSERBASE_BASE_URL
    api_key_config_field = "browserbase_api_key"
    project_id_config_field = "browserbase_project_id"
    base_url_config_field = "browserbase_base_url"

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
        super().__init__(api_key=api_key, base_url=base_url, transport=transport)
        self.project_id = self.config_text(project_id, self.project_id_env_var)
        self.proxies = bool(proxies)
        self.advanced_stealth = bool(advanced_stealth)
        self.keep_alive = bool(keep_alive)

    @classmethod
    def from_config(
        cls,
        browser_config: Any,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "BrowserbaseCloudProvider":
        return cls(
            api_key=cls.config_value(browser_config, cls.api_key_config_field),
            project_id=cls.config_value(browser_config, cls.project_id_config_field),
            base_url=cls.config_value(browser_config, cls.base_url_config_field),
            proxies=cls.config_value(browser_config, "browserbase_proxies", True),
            advanced_stealth=cls.config_value(browser_config, "browserbase_advanced_stealth", False),
            keep_alive=cls.config_value(browser_config, "browserbase_keep_alive", True),
            transport=transport,
        )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.project_id)

    def status(self) -> dict[str, Any]:
        return {
            **self.api_key_status(),
            "project_id": self.project_id,
        }

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        if not self.is_configured():
            raise BrowserRuntimeError("Browserbase requires browserbase_api_key and browserbase_project_id or BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID.")
        ttl = self.session_timeout_seconds(session_timeout)
        body: dict[str, Any] = {
            "projectId": self.project_id,
            "timeout": ttl * 1000,
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
            headers=self.json_api_key_headers(),
            json_body=body,
            timeout=timeout,
            error_prefix="Failed to create Browserbase session",
        )
        payload = self._json_object(response, "Browserbase session response")
        provider_session_id = self._required_text(payload, "id", "Browserbase session id")
        cdp_url = self._required_text(payload, "connectUrl", "Browserbase CDP URL")
        return self.cloud_session(provider_session_id, cdp_url, ttl)

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        return await self._close_with_request(
            provider_session_id,
            "POST",
            join_url_path(self.base_url, f"/v1/sessions/{provider_session_id}"),
            headers=self.json_api_key_headers(),
            json_body={"projectId": self.project_id, "status": "REQUEST_RELEASE"},
            timeout=timeout,
            error_prefix="Failed to close Browserbase session",
        )


class BrowserUseCloudProvider(CloudBrowserProvider):
    backend = "browser-use"
    display_name = "Browser Use"
    auth_header_name = "X-Browser-Use-API-Key"
    api_key_env_var = "BROWSER_USE_API_KEY"
    base_url_env_var = "BROWSER_USE_BASE_URL"
    default_base_url = DEFAULT_BROWSER_USE_BASE_URL
    api_key_config_field = "browser_use_api_key"
    base_url_config_field = "browser_use_base_url"

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        if not self.is_configured():
            raise BrowserRuntimeError("Browser Use requires browser_use_api_key or BROWSER_USE_API_KEY.")
        ttl = self.session_timeout_seconds(session_timeout)
        timeout_minutes = max(1, (ttl + 59) // 60)
        response = await self._request(
            "POST",
            join_url_path(self.base_url, "/browsers"),
            headers=self.json_api_key_headers(),
            json_body={"timeout": timeout_minutes},
            timeout=timeout,
            error_prefix="Failed to create Browser Use session",
        )
        payload = self._json_object(response, "Browser Use session response")
        provider_session_id = self._required_text(payload, "id", "Browser Use session id")
        cdp_url = str(payload.get("cdpUrl") or payload.get("connectUrl") or "").strip()
        if not cdp_url:
            raise BrowserRuntimeError("Browser Use session response did not include cdpUrl or connectUrl.")
        return self.cloud_session(provider_session_id, cdp_url, ttl)

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        return await self._close_with_request(
            provider_session_id,
            "PATCH",
            join_url_path(self.base_url, f"/browsers/{provider_session_id}"),
            headers=self.json_api_key_headers(),
            json_body={"action": "stop"},
            timeout=timeout,
            error_prefix="Failed to close Browser Use session",
        )


class FirecrawlCloudProvider(CloudBrowserProvider):
    backend = "firecrawl"
    display_name = "Firecrawl"
    auth_header_name = "Authorization"
    auth_header_prefix = "Bearer "
    api_key_env_var = "FIRECRAWL_API_KEY"
    base_url_env_var = "FIRECRAWL_API_URL"
    default_base_url = DEFAULT_FIRECRAWL_BROWSER_BASE_URL
    api_key_config_field = "firecrawl_api_key"
    base_url_config_field = "firecrawl_base_url"

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        if not self.is_configured():
            raise BrowserRuntimeError("Firecrawl browser sessions require firecrawl_api_key or FIRECRAWL_API_KEY.")
        ttl = self.session_timeout_seconds(session_timeout)
        response = await self._request(
            "POST",
            join_url_path(self.base_url, "/v2/browser"),
            headers=self.json_api_key_headers(),
            json_body={"ttl": ttl},
            timeout=timeout,
            error_prefix="Failed to create Firecrawl browser session",
        )
        payload = self._json_object(response, "Firecrawl browser session response")
        provider_session_id = self._required_text(payload, "id", "Firecrawl browser session id")
        cdp_url = self._required_text(payload, "cdpUrl", "Firecrawl CDP URL")
        return self.cloud_session(provider_session_id, cdp_url, ttl)

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        return await self._close_with_request(
            provider_session_id,
            "DELETE",
            join_url_path(self.base_url, f"/v2/browser/{provider_session_id}"),
            headers=self.json_api_key_headers(),
            timeout=timeout,
            error_prefix="Failed to close Firecrawl browser session",
        )
