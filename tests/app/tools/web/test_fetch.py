import asyncio
import json

from opensprite.app.tools.web.fetch import WebFetchTool
from opensprite.modules.tools.web_access_policy import looks_blocked_or_challenge


class _FakeFetcher:
    def __init__(
        self,
        max_chars=50000,
        max_response_size=5242880,
        timeout=30,
        prefer_trafilatura=True,
        firecrawl_api_key=None,
    ):
        self.max_chars = max_chars
        self.max_response_size = max_response_size
        self.timeout = timeout
        self.prefer_trafilatura = prefer_trafilatura
        self.firecrawl_api_key = firecrawl_api_key

    def fetch(self, url: str):
        return {
            "url": url,
            "finalUrl": f"{url}?ref=1",
            "status": 200,
            "title": "SQLite FTS5",
            "extractor": "trafilatura",
            "contentType": "text/html",
            "truncated": False,
            "text": "SQLite FTS5 supports full text search.",
        }


def test_web_fetch_returns_unified_web_payload(monkeypatch):
    monkeypatch.setattr(
        "opensprite.app.tools.web.fetch.WebFetcher",
        lambda *args, **kwargs: _FakeFetcher(),
    )
    tool = WebFetchTool()

    payload = json.loads(asyncio.run(tool._execute("https://sqlite.org/fts5.html")))

    assert payload == {
        "type": "web_fetch",
        "query": "https://sqlite.org/fts5.html",
        "url": "https://sqlite.org/fts5.html",
        "final_url": "https://sqlite.org/fts5.html?ref=1",
        "title": "SQLite FTS5",
        "content": "SQLite FTS5 supports full text search.",
        "summary": "SQLite FTS5",
        "provider": "web_fetch",
        "extractor": "trafilatura",
        "status": 200,
        "content_type": "text/html",
        "truncated": False,
        "content_chars": 38,
        "has_title": True,
        "has_main_content": False,
        "is_too_short": True,
        "blocked_or_challenge": False,
        "min_content_chars": 800,
        "items": [],
    }


def test_web_fetch_marks_blocked_challenge_payload(monkeypatch):
    class _BlockedFetcher(_FakeFetcher):
        def fetch(self, url: str):
            result = super().fetch(url)
            result.update(
                {
                    "status": 403,
                    "title": "Access Denied",
                    "text": "Captcha: verify you are human before continuing.",
                }
            )
            return result

    monkeypatch.setattr(
        "opensprite.app.tools.web.fetch.WebFetcher",
        lambda *args, **kwargs: _BlockedFetcher(),
    )
    tool = WebFetchTool()

    payload = json.loads(asyncio.run(tool._execute("https://example.com/blocked")))

    assert payload["blocked_or_challenge"] is True
    assert payload["has_main_content"] is False
    assert payload["is_too_short"] is True


def test_web_fetch_does_not_treat_rate_limit_topic_as_blocked(monkeypatch):
    class _RateLimitDocsFetcher(_FakeFetcher):
        def fetch(self, url: str):
            result = super().fetch(url)
            result.update(
                {
                    "title": "API Rate Limits",
                    "text": "This documentation explains API rate limits, quotas, and usage controls." * 20,
                }
            )
            return result

    monkeypatch.setattr(
        "opensprite.app.tools.web.fetch.WebFetcher",
        lambda *args, **kwargs: _RateLimitDocsFetcher(),
    )
    tool = WebFetchTool()

    payload = json.loads(asyncio.run(tool._execute("https://example.com/rate-limits")))

    assert payload["blocked_or_challenge"] is False
    assert payload["has_main_content"] is True


def test_web_blocking_rule_combines_status_and_challenge_text():
    assert looks_blocked_or_challenge(title="Anything", content="Regular page", status=403) is True
    assert (
        looks_blocked_or_challenge(
            title="Security Check",
            content="Please verify you are human before continuing.",
            status=200,
        )
        is True
    )
    assert (
        looks_blocked_or_challenge(
            title="API Rate Limits",
            content="This documentation explains rate limits and quotas.",
            status=200,
        )
        is False
    )


def test_web_fetch_parameter_default_uses_configured_max_chars():
    tool = WebFetchTool(max_chars=1234)

    max_chars_schema = tool.parameters["properties"]["max_chars"]

    assert max_chars_schema["default"] == 1234
    assert max_chars_schema["minimum"] == 1


def test_web_fetch_execute_uses_configured_max_chars_by_default(monkeypatch):
    created_fetchers = []

    def fake_fetcher(*args, **kwargs):
        fetcher = _FakeFetcher(**kwargs)
        created_fetchers.append(fetcher)
        return fetcher

    monkeypatch.setattr("opensprite.app.tools.web.fetch.WebFetcher", fake_fetcher)
    tool = WebFetchTool(max_chars=1234)

    asyncio.run(tool._execute("https://sqlite.org/fts5.html"))

    assert created_fetchers[-1].max_chars == 1234


def test_web_fetch_execute_uses_configured_max_response_size(monkeypatch):
    created_fetchers = []

    def fake_fetcher(*args, **kwargs):
        fetcher = _FakeFetcher(**kwargs)
        created_fetchers.append(fetcher)
        return fetcher

    monkeypatch.setattr("opensprite.app.tools.web.fetch.WebFetcher", fake_fetcher)
    tool = WebFetchTool(max_response_size=2048)

    asyncio.run(tool._execute("https://sqlite.org/fts5.html"))

    assert created_fetchers[-1].max_response_size == 2048


def test_web_fetch_execute_runs_fetcher_in_thread(monkeypatch):
    calls = []

    async def fake_to_thread(func, *args):
        calls.append((func, args))
        return func(*args)

    monkeypatch.setattr(
        "opensprite.app.tools.web.fetch.WebFetcher",
        lambda *args, **kwargs: _FakeFetcher(),
    )
    monkeypatch.setattr("opensprite.app.tools.web.fetch.asyncio.to_thread", fake_to_thread)
    tool = WebFetchTool()

    payload = json.loads(asyncio.run(tool._execute("https://sqlite.org/fts5.html")))

    assert payload["url"] == "https://sqlite.org/fts5.html"
    assert len(calls) == 1
    assert calls[0][1] == ("https://sqlite.org/fts5.html",)


def test_web_fetch_execute_allows_max_chars_override(monkeypatch):
    created_fetchers = []

    def fake_fetcher(*args, **kwargs):
        fetcher = _FakeFetcher(**kwargs)
        created_fetchers.append(fetcher)
        return fetcher

    monkeypatch.setattr("opensprite.app.tools.web.fetch.WebFetcher", fake_fetcher)
    tool = WebFetchTool(max_chars=1234)

    asyncio.run(tool._execute("https://sqlite.org/fts5.html", max_chars=4321))

    assert created_fetchers[-1].max_chars == 4321
