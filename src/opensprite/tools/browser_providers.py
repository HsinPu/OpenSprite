"""Cloud browser provider implementations."""

from __future__ import annotations

from typing import Any

import httpx

from ..config.defaults import (
    DEFAULT_BROWSER_USE_BASE_URL,
    DEFAULT_BROWSERBASE_BASE_URL,
    DEFAULT_FIRECRAWL_BROWSER_BASE_URL,
)
from .browser_provider_base import CloudBrowserProvider


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
    configured_error = "Browserbase requires browserbase_api_key and browserbase_project_id or BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID."
    create_request = ("POST", "/v1/sessions", "Failed to create Browserbase session")
    create_cdp_url_keys = ("connectUrl",)
    close_request = ("POST", "/v1/sessions/{provider_session_id}", "Failed to close Browserbase session")

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

    def close_session_json_body(self) -> dict[str, Any] | None:
        return {"projectId": self.project_id, "status": "REQUEST_RELEASE"}

    def create_session_json_body(self, ttl: int) -> dict[str, Any] | None:
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
        return body


class BrowserUseCloudProvider(CloudBrowserProvider):
    backend = "browser-use"
    display_name = "Browser Use"
    auth_header_name = "X-Browser-Use-API-Key"
    api_key_env_var = "BROWSER_USE_API_KEY"
    base_url_env_var = "BROWSER_USE_BASE_URL"
    default_base_url = DEFAULT_BROWSER_USE_BASE_URL
    api_key_config_field = "browser_use_api_key"
    base_url_config_field = "browser_use_base_url"
    configured_error = "Browser Use requires browser_use_api_key or BROWSER_USE_API_KEY."
    create_request = ("POST", "/browsers", "Failed to create Browser Use session")
    create_cdp_url_keys = ("cdpUrl", "connectUrl")
    create_cdp_url_missing_error = "Browser Use session response did not include cdpUrl or connectUrl."
    close_request = ("PATCH", "/browsers/{provider_session_id}", "Failed to close Browser Use session")
    close_json_body = {"action": "stop"}

    def create_session_json_body(self, ttl: int) -> dict[str, Any] | None:
        timeout_minutes = max(1, (ttl + 59) // 60)
        return {"timeout": timeout_minutes}


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
    configured_error = "Firecrawl browser sessions require firecrawl_api_key or FIRECRAWL_API_KEY."
    create_request = ("POST", "/v2/browser", "Failed to create Firecrawl browser session")
    create_response_label = "Firecrawl browser session response"
    create_session_id_label = "Firecrawl browser session id"
    close_request = ("DELETE", "/v2/browser/{provider_session_id}", "Failed to close Firecrawl browser session")

    def create_session_json_body(self, ttl: int) -> dict[str, Any] | None:
        return {"ttl": ttl}
