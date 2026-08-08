from types import SimpleNamespace

from opensprite.config.schema import BrowserToolConfig
from opensprite.integrations.browser.factory import (
    browser_cloud_status,
    cloud_provider_from_config,
)
from opensprite.integrations.browser.providers import BrowserUseCloudProvider


def test_browser_cloud_status_reports_registered_cloud_backends():
    status = browser_cloud_status(SimpleNamespace())

    assert set(status) == {"browserbase", "browser-use", "firecrawl"}
    assert status["browserbase"]["configured"] is False
    assert status["browser-use"]["configured"] is False
    assert status["firecrawl"]["configured"] is False


def test_cloud_provider_factory_uses_selected_browser_backend():
    provider = cloud_provider_from_config(
        BrowserToolConfig(
            enabled=True,
            backend="browser-use",
            browser_use_api_key="browser-use-key",
        )
    )

    assert isinstance(provider, BrowserUseCloudProvider)
    assert provider.is_configured() is True
