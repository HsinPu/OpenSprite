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
    provider_cls = BROWSER_CLOUD_PROVIDER_TYPES.get(backend)
    return provider_cls.from_config(browser_config, transport=transport) if provider_cls is not None else None


def browser_cloud_status(browser_config: Any) -> dict[str, dict[str, Any]]:
    return {
        backend: provider_cls.from_config(browser_config).status()
        for backend, provider_cls in BROWSER_CLOUD_PROVIDER_TYPES.items()
    }


BROWSER_CLOUD_PROVIDER_TYPES = {
    BrowserbaseCloudProvider.backend: BrowserbaseCloudProvider,
    BrowserUseCloudProvider.backend: BrowserUseCloudProvider,
    FirecrawlCloudProvider.backend: FirecrawlCloudProvider,
}
