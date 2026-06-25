"""Base types shared by cloud browser providers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config.defaults import DEFAULT_BROWSER_SESSION_TIMEOUT
from ..utils.url import join_url_path


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
    api_key_env_var = ""
    base_url_env_var = ""
    default_base_url = ""
    api_key_config_field = ""
    base_url_config_field = ""
    close_request: tuple[str, str, str] | None = None
    close_json_body: dict[str, Any] | None = None

    def __init__(
        self,
        *,
        api_key: Any = "",
        base_url: Any = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.transport = transport
        self.api_key = self.resolve_api_key(api_key)
        self.base_url = self.resolve_base_url(base_url)

    @classmethod
    def config_value(cls, browser_config: Any, field: str, default: Any = "") -> Any:
        return getattr(browser_config, field, default) if field else default

    @classmethod
    def from_config(
        cls,
        browser_config: Any,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "CloudBrowserProvider":
        return cls(
            api_key=cls.config_value(browser_config, cls.api_key_config_field),
            base_url=cls.config_value(browser_config, cls.base_url_config_field),
            transport=transport,
        )

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

    def config_text(self, value: Any, env_var: str) -> str:
        candidates = [value]
        if env_var:
            candidates.append(os.getenv(env_var))
        for candidate in candidates:
            text = str(candidate or "").strip()
            if text:
                return text
        return ""

    def config_base_url(self, value: Any, env_var: str, default: str) -> str:
        return (self.config_text(value, env_var) or default).rstrip("/")

    def resolve_api_key(self, value: Any) -> str:
        return self.config_text(value, self.api_key_env_var)

    def resolve_base_url(self, value: Any) -> str:
        return self.config_base_url(value, self.base_url_env_var, self.default_base_url)

    def json_api_key_headers(self) -> dict[str, str]:
        auth_header_value = f"{self.auth_header_prefix}{getattr(self, 'api_key', '')}"
        return {
            "Content-Type": "application/json",
            self.auth_header_name: auth_header_value,
        }

    def cloud_session(self, provider_session_id: str, cdp_url: str, ttl: int) -> CloudBrowserSession:
        return CloudBrowserSession(
            provider_session_id=provider_session_id,
            cdp_url=cdp_url,
            expires_at=time.monotonic() + ttl,
        )

    def _json_object(self, response: httpx.Response, label: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise BrowserRuntimeError(f"{label} was not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise BrowserRuntimeError(f"{label} was not a JSON object.")
        return payload

    def _required_text(self, payload: dict[str, Any], key: str, label: str) -> str:
        value = str(payload.get(key) or "").strip()
        if not value:
            raise BrowserRuntimeError(f"{label} was missing from provider response.")
        return value

    def create_session_json_body(self, ttl: int) -> dict[str, Any] | None:
        return None

    async def create_session(self, *, session_key: str, session_timeout: int, timeout: int) -> CloudBrowserSession:
        del session_key
        create_request = getattr(self, "create_request", None)
        if create_request is None:
            raise NotImplementedError
        if not self.is_configured():
            configured_error = getattr(self, "configured_error", "")
            raise BrowserRuntimeError(configured_error or f"{self.display_name} is not configured.")
        ttl = self.session_timeout_seconds(session_timeout)
        method, path, error_prefix = create_request
        response = await self._request(
            method,
            join_url_path(self.base_url, path),
            headers=self.json_api_key_headers(),
            json_body=self.create_session_json_body(ttl),
            timeout=timeout,
            error_prefix=error_prefix,
        )
        response_label = getattr(self, "create_response_label", "") or f"{self.display_name} session response"
        provider_session_id_label = getattr(self, "create_session_id_label", "") or f"{self.display_name} session id"
        cdp_url_label = f"{self.display_name} CDP URL"
        payload = self._json_object(response, response_label)
        provider_session_id = self._required_text(payload, "id", provider_session_id_label)
        create_cdp_url_keys = getattr(self, "create_cdp_url_keys", ("cdpUrl",))
        cdp_url = next(
            (
                value
                for key in create_cdp_url_keys
                if (value := str(payload.get(key) or "").strip())
            ),
            "",
        )
        if not cdp_url:
            missing_error = getattr(self, "create_cdp_url_missing_error", "")
            raise BrowserRuntimeError(
                missing_error or f"{cdp_url_label} was missing from provider response."
            )
        return self.cloud_session(provider_session_id, cdp_url, ttl)

    def close_session_json_body(self) -> dict[str, Any] | None:
        return self.close_json_body

    async def close_session(self, provider_session_id: str, *, timeout: int) -> bool:
        if self.close_request is None:
            return False
        method, path_template, error_prefix = self.close_request
        return await self._close_with_request(
            provider_session_id,
            method,
            join_url_path(
                self.base_url,
                path_template.format(provider_session_id=provider_session_id),
            ),
            headers=self.json_api_key_headers(),
            json_body=self.close_session_json_body(),
            timeout=timeout,
            error_prefix=error_prefix,
        )

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
