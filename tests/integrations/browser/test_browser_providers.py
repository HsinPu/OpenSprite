import asyncio
import json

import httpx

from opensprite.integrations.browser.providers import (
    BrowserUseCloudProvider,
    BrowserbaseCloudProvider,
    FirecrawlCloudProvider,
)


def test_browserbase_provider_creates_and_closes_cdp_session():
    requests = []

    async def handler(request):
        requests.append(request)
        if request.method == "POST" and request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"id": "bb-session-1", "connectUrl": "ws://browserbase/cdp"})
        if request.method == "POST" and request.url.path == "/v1/sessions/bb-session-1":
            return httpx.Response(204)
        return httpx.Response(404, text="not found")

    provider = BrowserbaseCloudProvider(
        api_key="bb-key",
        project_id="project-1",
        base_url="https://browserbase.test",
        transport=httpx.MockTransport(handler),
    )

    session = asyncio.run(provider.create_session(session_key="chat-1", session_timeout=300, timeout=9))
    closed = asyncio.run(provider.close_session(session.provider_session_id, timeout=9))

    create_body = json.loads(requests[0].content.decode("utf-8"))
    close_body = json.loads(requests[1].content.decode("utf-8"))
    assert session.provider_session_id == "bb-session-1"
    assert session.cdp_url == "ws://browserbase/cdp"
    assert closed is True
    assert requests[0].headers["X-BB-API-Key"] == "bb-key"
    assert create_body["projectId"] == "project-1"
    assert create_body["timeout"] == 300000
    assert close_body == {"projectId": "project-1", "status": "REQUEST_RELEASE"}


def test_browserbase_provider_avoids_duplicate_v1_path():
    requests = []

    async def handler(request):
        requests.append(request)
        if request.method == "POST" and request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"id": "bb-session-1", "connectUrl": "ws://browserbase/cdp"})
        if request.method == "POST" and request.url.path == "/v1/sessions/bb-session-1":
            return httpx.Response(204)
        return httpx.Response(404, text="not found")

    provider = BrowserbaseCloudProvider(
        api_key="bb-key",
        project_id="project-1",
        base_url="https://browserbase.test/v1",
        transport=httpx.MockTransport(handler),
    )

    session = asyncio.run(provider.create_session(session_key="chat-1", session_timeout=300, timeout=9))
    closed = asyncio.run(provider.close_session(session.provider_session_id, timeout=9))

    assert closed is True
    assert [request.url.path for request in requests] == ["/v1/sessions", "/v1/sessions/bb-session-1"]


def test_browser_use_provider_creates_cdp_session():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "bu-session-1", "cdpUrl": "ws://browser-use/cdp"})

    provider = BrowserUseCloudProvider(
        api_key="bu-key",
        base_url="https://browser-use.test/api/v3",
        transport=httpx.MockTransport(handler),
    )

    session = asyncio.run(provider.create_session(session_key="chat-1", session_timeout=300, timeout=9))

    body = json.loads(requests[0].content.decode("utf-8"))
    assert session.provider_session_id == "bu-session-1"
    assert session.cdp_url == "ws://browser-use/cdp"
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v3/browsers"
    assert requests[0].headers["X-Browser-Use-API-Key"] == "bu-key"
    assert body == {"timeout": 5}


def test_browser_use_provider_accepts_full_browsers_base_url():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "bu-session-1", "cdpUrl": "ws://browser-use/cdp"})

    provider = BrowserUseCloudProvider(
        api_key="bu-key",
        base_url="https://browser-use.test/api/v3/browsers",
        transport=httpx.MockTransport(handler),
    )

    asyncio.run(provider.create_session(session_key="chat-1", session_timeout=300, timeout=9))

    assert requests[0].url.path == "/api/v3/browsers"


def test_firecrawl_provider_creates_cdp_session():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "fc-session-1", "cdpUrl": "ws://firecrawl/cdp"})

    provider = FirecrawlCloudProvider(
        api_key="fc-key",
        base_url="https://firecrawl.test",
        transport=httpx.MockTransport(handler),
    )

    session = asyncio.run(provider.create_session(session_key="chat-1", session_timeout=120, timeout=9))

    body = json.loads(requests[0].content.decode("utf-8"))
    assert session.provider_session_id == "fc-session-1"
    assert session.cdp_url == "ws://firecrawl/cdp"
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v2/browser"
    assert requests[0].headers["Authorization"] == "Bearer fc-key"
    assert body == {"ttl": 120}


def test_firecrawl_provider_avoids_duplicate_v2_path():
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "fc-session-1", "cdpUrl": "ws://firecrawl/cdp"})

    provider = FirecrawlCloudProvider(
        api_key="fc-key",
        base_url="https://firecrawl.test/v2",
        transport=httpx.MockTransport(handler),
    )

    asyncio.run(provider.create_session(session_key="chat-1", session_timeout=120, timeout=9))

    assert requests[0].url.path == "/v2/browser"
