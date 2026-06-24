"""Cloud browser provider selection helpers."""

from __future__ import annotations

from typing import Any

import httpx

from ..config.defaults import DEFAULT_BROWSER_BACKEND
from .browser_provider_base import CloudBrowserProvider


def cloud_provider_from_config(
    browser_config: Any,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CloudBrowserProvider | None:
    backend = str(getattr(browser_config, "backend", DEFAULT_BROWSER_BACKEND) or DEFAULT_BROWSER_BACKEND).strip()
    browserbase_cls, browser_use_cls, firecrawl_cls = _provider_classes()
    if backend == "browserbase":
        return browserbase_cls(
            api_key=getattr(browser_config, "browserbase_api_key", ""),
            project_id=getattr(browser_config, "browserbase_project_id", ""),
            base_url=getattr(browser_config, "browserbase_base_url", ""),
            proxies=getattr(browser_config, "browserbase_proxies", True),
            advanced_stealth=getattr(browser_config, "browserbase_advanced_stealth", False),
            keep_alive=getattr(browser_config, "browserbase_keep_alive", True),
            transport=transport,
        )
    if backend == "browser-use":
        return browser_use_cls(
            api_key=getattr(browser_config, "browser_use_api_key", ""),
            base_url=getattr(browser_config, "browser_use_base_url", ""),
            transport=transport,
        )
    if backend == "firecrawl":
        return firecrawl_cls(
            api_key=getattr(browser_config, "firecrawl_api_key", ""),
            base_url=getattr(browser_config, "firecrawl_base_url", ""),
            transport=transport,
        )
    return None


def browser_cloud_status(browser_config: Any) -> dict[str, dict[str, Any]]:
    browserbase_cls, browser_use_cls, firecrawl_cls = _provider_classes()
    return {
        "browserbase": browserbase_cls(
            api_key=getattr(browser_config, "browserbase_api_key", ""),
            project_id=getattr(browser_config, "browserbase_project_id", ""),
            base_url=getattr(browser_config, "browserbase_base_url", ""),
            proxies=getattr(browser_config, "browserbase_proxies", True),
            advanced_stealth=getattr(browser_config, "browserbase_advanced_stealth", False),
            keep_alive=getattr(browser_config, "browserbase_keep_alive", True),
        ).status(),
        "browser-use": browser_use_cls(
            api_key=getattr(browser_config, "browser_use_api_key", ""),
            base_url=getattr(browser_config, "browser_use_base_url", ""),
        ).status(),
        "firecrawl": firecrawl_cls(
            api_key=getattr(browser_config, "firecrawl_api_key", ""),
            base_url=getattr(browser_config, "firecrawl_base_url", ""),
        ).status(),
    }


def _provider_classes():
    from .browser_runtime import BrowserUseCloudProvider, BrowserbaseCloudProvider, FirecrawlCloudProvider

    return BrowserbaseCloudProvider, BrowserUseCloudProvider, FirecrawlCloudProvider
