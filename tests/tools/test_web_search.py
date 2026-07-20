import asyncio
import builtins
import json
import sys
import types

import pytest

from opensprite.config.schema import WebSearchToolConfig
from opensprite.tools.web_search import WebSearchTool
from opensprite.tools.web_search_freshness import (
    freshness_params as _freshness_params,
    normalize_freshness as _normalize_freshness,
)
from opensprite.tools.web_search_payloads import (
    format_error as _format_error,
    format_results as _format_results,
)
from opensprite.utils.searxng_url import SEARXNG_MAX_RESPONSE_BYTES, searxng_endpoint_url


class _FakeSearxngResponse:
    def __init__(self, results=None, *, payload_bytes=None, headers=None, fail_on_read=False):
        self.results = (
            results
            if results is not None
            else [{"title": "One", "url": "https://example.com/one", "content": "First"}]
        )
        self.payload_bytes = payload_bytes
        self.headers = headers or {}
        self.fail_on_read = fail_on_read

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def raise_for_status(self):
        return None

    def json(self):
        return {"results": self.results}

    async def aiter_bytes(self):
        if self.fail_on_read:
            raise AssertionError("compressed SearXNG body must not be read")
        yield self.payload_bytes or json.dumps(self.json()).encode("utf-8")


class _FakeSearxngClient:
    def __init__(self):
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, method, url, params=None, headers=None, timeout=None):
        assert method == "GET"
        self.requests.append((url, params, headers))
        return _FakeSearxngResponse()


class _FakeEmptySearxngClient(_FakeSearxngClient):
    def stream(self, method, url, params=None, headers=None, timeout=None):
        assert method == "GET"
        self.requests.append((url, params, headers))
        return _FakeSearxngResponse([])


class _FakeMalformedSearxngClient(_FakeSearxngClient):
    def stream(self, method, url, params=None, headers=None, timeout=None):
        assert method == "GET"
        self.requests.append((url, params, headers))
        return _FakeSearxngResponse(
            [
                {"title": "", "url": "https://example.com/no-title", "content": "bad"},
                {"title": "No URL", "url": "", "content": "bad"},
                None,
            ]
        )


class _FakePagedSearxngClient:
    def __init__(self):
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, method, url, params=None, headers=None, timeout=None):
        assert method == "GET"
        self.requests.append((url, params, headers))
        page = int((params or {}).get("pageno") or 1)
        results_by_page = {
            1: [{"title": "One", "url": "https://example.com/one", "content": "First"}],
            2: [{"title": "Two", "url": "https://example.com/two", "content": "Second"}],
            3: [{"title": "Three", "url": "https://example.com/three", "content": "Third"}],
        }
        return _FakeSearxngResponse(results_by_page.get(page, []))


class _FakeOversizedSearxngClient(_FakeSearxngClient):
    def stream(self, method, url, params=None, headers=None, timeout=None):
        assert method == "GET"
        self.requests.append((url, params, headers))
        return _FakeSearxngResponse(payload_bytes=b"x" * (SEARXNG_MAX_RESPONSE_BYTES + 1))


class _FakeCompressedSearxngClient(_FakeSearxngClient):
    def stream(self, method, url, params=None, headers=None, timeout=None):
        assert method == "GET"
        self.requests.append((url, params, headers))
        return _FakeSearxngResponse(
            headers={"content-encoding": "gzip"},
            fail_on_read=True,
        )


def _install_fake_ddgs(monkeypatch, *, text_results=None, text_raises=None):
    fake = types.ModuleType("ddgs")
    fake.calls = []

    class _FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def text(self, query, **kwargs):
            fake.calls.append((query, kwargs))
            if text_raises is not None:
                raise text_raises
            yield from (text_results or [])

    fake.DDGS = _FakeDDGS
    monkeypatch.setitem(sys.modules, "ddgs", fake)
    return fake


def _disable_ddgs(monkeypatch):
    monkeypatch.delitem(sys.modules, "ddgs", raising=False)
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "ddgs":
            raise ImportError("blocked for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)


def test_format_results_returns_structured_json_payload():
    payload = _format_results(
        "sqlite fts5",
        [
            {
                "title": "<b>SQLite FTS5</b>",
                "url": "https://sqlite.org/fts5.html",
                "content": "Official   <em>full text</em> search docs",
            }
        ],
        5,
        provider="duckduckgo",
        backend="ddgs",
    )

    parsed = json.loads(payload)

    assert parsed == {
        "type": "web_search",
        "ok": True,
        "query": "sqlite fts5",
        "summary": "Search results for: sqlite fts5",
        "provider": "duckduckgo",
        "backend": "ddgs",
        "items": [
            {
                "title": "SQLite FTS5",
                "url": "https://sqlite.org/fts5.html",
                "content": "Official full text search docs",
            }
        ],
    }


def test_format_results_includes_optional_metadata():
    payload = _format_results(
        "sqlite fts5",
        [{"title": "SQLite", "url": "https://sqlite.org/", "content": ""}],
        1,
        provider="duckduckgo",
        backend="ddgs",
    )

    assert json.loads(payload)["backend"] == "ddgs"


def test_format_error_returns_structured_json_payload():
    payload = _format_error("sqlite fts", "duckduckgo", "DuckDuckGo returned no results")

    parsed = json.loads(payload)

    assert parsed["type"] == "web_search"
    assert parsed["ok"] is False
    assert parsed["query"] == "sqlite fts"
    assert parsed["provider"] == "duckduckgo"
    assert parsed["items"] == []
    assert parsed["error"] == "DuckDuckGo returned no results"
    assert parsed["error_type"] == "WebSearchError"
    assert parsed["category"] == "web_search_error"


def test_web_search_count_limit_comes_from_config():
    tool = WebSearchTool(config=WebSearchToolConfig(max_results=25))

    count_schema = tool.parameters["properties"]["count"]
    freshness_schema = tool.parameters["properties"]["freshness"]

    assert count_schema["maximum"] == 25
    assert count_schema["default"] == 25
    assert count_schema["description"] == "Results (1-25)"
    assert freshness_schema["default"] == "none"
    assert freshness_schema["enum"] == ["none", "day", "week", "month", "year"]


def test_web_search_execute_clamps_to_configured_max_results(monkeypatch):
    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", max_results=25))
    requested_counts = []

    async def fake_search(query, n, freshness):
        requested_counts.append((n, freshness))
        return _format_results(query, [], n, provider="duckduckgo", backend="ddgs")

    monkeypatch.setattr(tool, "_search_duckduckgo", fake_search)

    asyncio.run(tool._execute("sqlite", count=50))

    assert requested_counts == [(25, "none")]


def test_web_search_execute_allows_freshness_override(monkeypatch):
    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", freshness="year"))
    requested_freshness = []

    async def fake_search(query, n, freshness):
        requested_freshness.append(freshness)
        return _format_results(query, [], n, provider="duckduckgo", backend="ddgs")

    monkeypatch.setattr(tool, "_search_duckduckgo", fake_search)

    asyncio.run(tool._execute("sqlite docs", freshness="none"))

    assert requested_freshness == ["none"]


def test_web_search_execute_respects_any_time_for_latest_query(monkeypatch):
    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", freshness="none"))
    requested_freshness = []

    async def fake_search(query, n, freshness):
        requested_freshness.append(freshness)
        return _format_results(query, [], n, provider="duckduckgo", backend="ddgs")

    monkeypatch.setattr(tool, "_search_duckduckgo", fake_search)

    asyncio.run(tool._execute("Qwen latest model 2026"))

    assert requested_freshness == ["none"]


def test_web_search_freshness_values_and_provider_params():
    assert _normalize_freshness("month", "year") == "month"
    assert _normalize_freshness("latest", "year") == "year"
    assert _freshness_params("searxng", "year") == {"time_range": "year"}
    assert _freshness_params("searxng", "none") == {}


@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        ("https://searx.test/search", "https://searx.test/search"),
        (
            "https://searx.test/searx/config?lang=zh#metadata",
            "https://searx.test/searx/search",
        ),
        (
            "https://searx.test/searx/?lang=zh#metadata",
            "https://searx.test/searx/search",
        ),
        (
            "https://searx.test/search/",
            "https://searx.test/search/search",
        ),
    ],
)
def test_searxng_search_normalizes_endpoint_url(monkeypatch, base_url, expected_url):
    fake_client = _FakeSearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(config=WebSearchToolConfig(provider="searxng", searxng_url=base_url))

    payload = json.loads(asyncio.run(tool._search_searxng("sqlite", 1, "none")))

    assert payload["items"][0]["title"] == "One"
    assert fake_client.requests[0][0] == expected_url
    assert fake_client.requests[0][1]["pageno"] == 1
    assert fake_client.requests[0][2]["Accept-Encoding"] == "identity"


@pytest.mark.parametrize(
    "base_url",
    ["", "searx.test/search", "ftp://searx.test/search", "https:///search"],
)
def test_searxng_endpoint_url_requires_absolute_http_url(base_url):
    with pytest.raises(ValueError, match=r"absolute HTTP\(S\) URL with a hostname"):
        searxng_endpoint_url(base_url, "/search")


def test_searxng_search_sends_configured_engines_and_categories(monkeypatch):
    fake_client = _FakeSearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(
        config=WebSearchToolConfig(
            provider="searxng",
            searxng_engines=["google", "bing"],
            searxng_categories=["general", "news"],
        )
    )

    json.loads(asyncio.run(tool._search_searxng("sqlite", 1, "none")))

    assert fake_client.requests[0][1]["engines"] == "google,bing"
    assert fake_client.requests[0][1]["categories"] == "general,news"


def test_searxng_search_fetches_multiple_pages(monkeypatch):
    fake_client = _FakePagedSearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(config=WebSearchToolConfig(provider="searxng", max_results=3, searxng_max_pages=3))

    payload = json.loads(asyncio.run(tool._search_searxng("sqlite", 3, "week")))

    assert payload["freshness"] == "week"
    assert [item["title"] for item in payload["items"]] == ["One", "Two", "Three"]
    assert [request[1]["pageno"] for request in fake_client.requests] == [1, 2, 3]
    assert all(request[1]["time_range"] == "week" for request in fake_client.requests)


def test_searxng_search_respects_configured_page_limit(monkeypatch):
    fake_client = _FakePagedSearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(config=WebSearchToolConfig(provider="searxng", max_results=3, searxng_max_pages=1))

    payload = json.loads(asyncio.run(tool._search_searxng("sqlite", 3, "none")))

    assert [item["title"] for item in payload["items"]] == ["One"]
    assert [request[1]["pageno"] for request in fake_client.requests] == [1]


def test_searxng_search_reports_empty_results(monkeypatch):
    fake_client = _FakeEmptySearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(
        config=WebSearchToolConfig(provider="searxng", searxng_url="https://searx.test")
    )

    payload = json.loads(asyncio.run(tool._search_searxng("no matches", 3, "none")))

    assert payload["ok"] is False
    assert payload["provider"] == "searxng"
    assert payload["backend"] == "searxng"
    assert payload["items"] == []
    assert payload["error"] == "SearXNG returned no results for 'no matches'."


def test_searxng_search_rejects_untraceable_results(monkeypatch):
    fake_client = _FakeMalformedSearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(
        config=WebSearchToolConfig(provider="searxng", searxng_url="https://searx.test")
    )

    payload = json.loads(asyncio.run(tool._search_searxng("malformed", 3, "none")))

    assert payload["ok"] is False
    assert payload["items"] == []
    assert payload["error"] == "SearXNG returned no results for 'malformed'."


def test_searxng_search_rejects_oversized_decoded_response(monkeypatch):
    fake_client = _FakeOversizedSearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(
        config=WebSearchToolConfig(provider="searxng", searxng_url="https://searx.test")
    )

    payload = json.loads(asyncio.run(tool._search_searxng("oversized", 3, "none")))

    assert payload["ok"] is False
    assert payload["items"] == []
    assert payload["error"] == f"SearXNG response exceeded {SEARXNG_MAX_RESPONSE_BYTES} bytes"


def test_searxng_search_rejects_compressed_response_before_reading_body(monkeypatch):
    fake_client = _FakeCompressedSearxngClient()
    monkeypatch.setattr(
        "opensprite.tools.web_search.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )
    tool = WebSearchTool(
        config=WebSearchToolConfig(provider="searxng", searxng_url="https://searx.test")
    )

    payload = json.loads(asyncio.run(tool._search_searxng("compressed", 3, "none")))

    assert payload["ok"] is False
    assert payload["error"] == "SearXNG compressed responses are not accepted"


def test_duckduckgo_search_prefers_ddgs_package(monkeypatch):
    fake = _install_fake_ddgs(
        monkeypatch,
        text_results=[
            {"title": "Qwen latest", "href": "https://qwen.ai/blog/", "body": "Recent Qwen updates"},
            {"title": "Qwen models", "url": "https://huggingface.co/Qwen", "body": "Model releases"},
        ],
    )

    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", max_results=2))

    payload = json.loads(asyncio.run(tool._search_duckduckgo("Qwen latest model", 2, "month")))

    assert payload["provider"] == "duckduckgo"
    assert payload["backend"] == "ddgs"
    assert payload["freshness"] == "month"
    assert [item["url"] for item in payload["items"]] == [
        "https://qwen.ai/blog/",
        "https://huggingface.co/Qwen",
    ]
    assert fake.calls == [("Qwen latest model", {"max_results": 2, "timelimit": "m"})]


def test_duckduckgo_search_reports_missing_ddgs(monkeypatch):
    _disable_ddgs(monkeypatch)
    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", max_results=1))

    payload = json.loads(asyncio.run(tool._search_duckduckgo("sqlite", 1, "none")))

    assert payload["ok"] is False
    assert payload["provider"] == "duckduckgo"
    assert payload["backend"] == "ddgs"
    assert payload["freshness"] == "none"
    assert payload["items"] == []
    assert "ddgs package is not installed" in payload["error"]


def test_duckduckgo_search_reports_ddgs_no_results(monkeypatch):
    fake = _install_fake_ddgs(monkeypatch, text_results=[])
    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", max_results=1))

    payload = json.loads(asyncio.run(tool._search_duckduckgo("sqlite", 1, "none")))

    assert payload["ok"] is False
    assert payload["provider"] == "duckduckgo"
    assert payload["backend"] == "ddgs"
    assert payload["freshness"] == "none"
    assert payload["items"] == []
    assert payload["error"] == "DDGS returned no results for 'sqlite'."
    assert fake.calls == [("sqlite", {"max_results": 1})]


def test_duckduckgo_search_reports_ddgs_runtime_error(monkeypatch):
    _install_fake_ddgs(monkeypatch, text_raises=RuntimeError("rate limited 202"))
    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", max_results=1))

    payload = json.loads(asyncio.run(tool._search_duckduckgo("sqlite", 1, "week")))

    assert payload["ok"] is False
    assert payload["provider"] == "duckduckgo"
    assert payload["backend"] == "ddgs"
    assert payload["freshness"] == "week"
    assert "rate limited 202" in payload["error"]


def test_duckduckgo_search_does_not_drop_freshness_when_ddgs_rejects_timelimit(monkeypatch):
    fake = _install_fake_ddgs(
        monkeypatch,
        text_raises=TypeError("DDGS.text() got an unexpected keyword argument 'timelimit'"),
    )
    tool = WebSearchTool(config=WebSearchToolConfig(provider="duckduckgo", max_results=1))

    payload = json.loads(asyncio.run(tool._search_duckduckgo("sqlite", 1, "week")))

    assert payload["ok"] is False
    assert payload["provider"] == "duckduckgo"
    assert payload["backend"] == "ddgs"
    assert payload["freshness"] == "week"
    assert "unexpected keyword argument 'timelimit'" in payload["error"]
    assert fake.calls == [("sqlite", {"max_results": 1, "timelimit": "w"})]
