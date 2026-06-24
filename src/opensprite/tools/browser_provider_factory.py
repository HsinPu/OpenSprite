"""Cloud browser provider selection helpers."""

from __future__ import annotations

from typing import Any

import httpx

from ..config.defaults import DEFAULT_BROWSER_BACKEND
from .browser_provider_base import CloudBrowserProvider
from .browser_providers import BrowserUseCloudProvider, BrowserbaseCloudProvider, FirecrawlCloudProvider


def cloud_provider_from_config(
    browser_config: Any,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CloudBrowserProvider | None:
    backend = str(getattr(browser_config, "backend", DEFAULT_BROWSER_BACKEND) or DEFAULT_BROWSER_BACKEND).strip()
    factories = {
        "browserbase": _browserbase_provider,
        "browser-use": _browser_use_provider,
        "firecrawl": _firecrawl_provider,
    }
    factory = factories.get(backend)
    return factory(browser_config, transport=transport) if factory is not None else None


def browser_cloud_status(browser_config: Any) -> dict[str, dict[str, Any]]:
    return {
        "browserbase": _browserbase_provider(browser_config).status(),
        "browser-use": _browser_use_provider(browser_config).status(),
        "firecrawl": _firecrawl_provider(browser_config).status(),
    }


def _browserbase_provider(
    browser_config: Any,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BrowserbaseCloudProvider:
    return BrowserbaseCloudProvider(
        api_key=getattr(browser_config, "browserbase_api_key", ""),
        project_id=getattr(browser_config, "browserbase_project_id", ""),
        base_url=getattr(browser_config, "browserbase_base_url", ""),
        proxies=getattr(browser_config, "browserbase_proxies", True),
        advanced_stealth=getattr(browser_config, "browserbase_advanced_stealth", False),
        keep_alive=getattr(browser_config, "browserbase_keep_alive", True),
        transport=transport,
    )


def _browser_use_provider(
    browser_config: Any,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BrowserUseCloudProvider:
    return BrowserUseCloudProvider(
        api_key=getattr(browser_config, "browser_use_api_key", ""),
        base_url=getattr(browser_config, "browser_use_base_url", ""),
        transport=transport,
    )


def _firecrawl_provider(
    browser_config: Any,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FirecrawlCloudProvider:
    return FirecrawlCloudProvider(
        api_key=getattr(browser_config, "firecrawl_api_key", ""),
        base_url=getattr(browser_config, "firecrawl_base_url", ""),
        transport=transport,
    )
