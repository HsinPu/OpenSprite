import json
import asyncio
import socket
import gzip
import io
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import opensprite.tools.web_fetch as web_fetch_module
from opensprite.tools.web_blocking import looks_blocked_or_challenge
from opensprite.tools.web_fetch import (
    WebFetcher,
    WebFetchTool,
    _decode_response_body,
    _do_fetch,
    extract_with_firecrawl,
    fetch_url,
    validate_url,
)


def _public_getaddrinfo(host, port=None, *args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 443))]


class _TrackingStream:
    def __init__(self, content: bytes):
        self._buffer = io.BytesIO(content)
        self.bytes_read = 0

    def read(self, size=-1):
        chunk = self._buffer.read(size)
        self.bytes_read += len(chunk)
        return chunk


class _StreamingResponse:
    def __init__(
        self,
        content: bytes,
        *,
        headers: dict[str, str] | None = None,
        is_success: bool = True,
        encoding: str | None = "utf-8",
    ):
        self.is_success = is_success
        self.headers = headers or {}
        self.encoding = encoding
        self.raw = _TrackingStream(content)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def iter_raw(self, chunk_size=64 * 1024):
        while True:
            chunk = self.raw.read(chunk_size)
            if not chunk:
                return
            yield chunk


def _install_firecrawl_response(monkeypatch, response):
    calls = []

    def stream(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr(
        web_fetch_module.httpx,
        "stream",
        stream,
    )
    return calls


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
    monkeypatch.setattr("opensprite.tools.web_fetch.WebFetcher", lambda *args, **kwargs: _FakeFetcher())
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

    monkeypatch.setattr("opensprite.tools.web_fetch.WebFetcher", lambda *args, **kwargs: _BlockedFetcher())
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

    monkeypatch.setattr("opensprite.tools.web_fetch.WebFetcher", lambda *args, **kwargs: _RateLimitDocsFetcher())
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

    monkeypatch.setattr("opensprite.tools.web_fetch.WebFetcher", fake_fetcher)
    tool = WebFetchTool(max_chars=1234)

    asyncio.run(tool._execute("https://sqlite.org/fts5.html"))

    assert created_fetchers[-1].max_chars == 1234


def test_web_fetch_execute_uses_configured_max_response_size(monkeypatch):
    created_fetchers = []

    def fake_fetcher(*args, **kwargs):
        fetcher = _FakeFetcher(**kwargs)
        created_fetchers.append(fetcher)
        return fetcher

    monkeypatch.setattr("opensprite.tools.web_fetch.WebFetcher", fake_fetcher)
    tool = WebFetchTool(max_response_size=2048)

    asyncio.run(tool._execute("https://sqlite.org/fts5.html"))

    assert created_fetchers[-1].max_response_size == 2048


def test_web_fetch_execute_runs_fetcher_in_thread(monkeypatch):
    calls = []

    async def fake_to_thread(func, *args):
        calls.append((func, args))
        return func(*args)

    monkeypatch.setattr("opensprite.tools.web_fetch.WebFetcher", lambda *args, **kwargs: _FakeFetcher())
    monkeypatch.setattr("opensprite.tools.web_fetch.asyncio.to_thread", fake_to_thread)
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

    monkeypatch.setattr("opensprite.tools.web_fetch.WebFetcher", fake_fetcher)
    tool = WebFetchTool(max_chars=1234)

    asyncio.run(tool._execute("https://sqlite.org/fts5.html", max_chars=4321))

    assert created_fetchers[-1].max_chars == 4321


def test_web_fetcher_passes_configured_response_size_to_fetch_layer(monkeypatch):
    captured = {}

    def fake_fetch_url(*args, **kwargs):
        captured["max_response_size"] = args[2]
        return "text/plain", b"ab", 200, "https://example.com"

    monkeypatch.setattr("opensprite.tools.web_fetch.fetch_url", fake_fetch_url)
    fetcher = WebFetcher(max_response_size=2)

    fetcher.fetch("https://example.com")

    assert captured["max_response_size"] == 2


def test_fetch_url_does_not_retry_cloudflare_challenges(monkeypatch):
    calls = []

    def fake_do_fetch(url, timeout, user_agent, max_response_size):
        calls.append((url, timeout, user_agent, max_response_size))
        return b"blocked", 403, {"cf-mitigated": "challenge"}, url

    monkeypatch.setattr("opensprite.tools.web_fetch._do_fetch", fake_do_fetch)

    result = fetch_url("https://example.com/blocked", timeout=12, max_response_size=1024)

    assert result == ("text/html", b"blocked", 403, "https://example.com/blocked")
    assert len(calls) == 1


def test_extract_with_firecrawl_streams_normal_provider_response(monkeypatch):
    body = json.dumps(
        {
            "success": True,
            "data": {
                "markdown": "Readable provider content.",
                "metadata": {
                    "title": "Provider result",
                    "sourceURL": "https://example.com/final",
                    "statusCode": 200,
                },
            },
        }
    ).encode("utf-8")
    response = _StreamingResponse(body)
    calls = _install_firecrawl_response(monkeypatch, response)

    result = extract_with_firecrawl(
        "https://example.com/article",
        "markdown",
        "configured-key",
        12,
        len(body),
    )

    assert result == {
        "text": "Readable provider content.",
        "extractor": "firecrawl",
        "title": "Provider result",
        "finalUrl": "https://example.com/final",
        "status": 200,
    }
    assert response.raw.bytes_read == len(body)
    assert response.closed is True
    assert len(calls) == 1
    assert calls[0][0][:2] == (
        "POST",
        f"{web_fetch_module.DEFAULT_FIRECRAWL_BASE_URL}/v2/scrape",
    )
    assert calls[0][1]["timeout"] == 12
    assert calls[0][1]["headers"]["Accept-Encoding"] == "identity"


def test_extract_with_firecrawl_stops_reading_provider_response_over_limit(
    monkeypatch,
):
    max_response_size = 64
    body = json.dumps(
        {
            "success": True,
            "data": {"markdown": "A" * 4096},
        }
    ).encode("utf-8")
    assert len(body) > max_response_size
    response = _StreamingResponse(body)
    _install_firecrawl_response(monkeypatch, response)

    result = extract_with_firecrawl(
        "https://example.com/article",
        "markdown",
        "configured-key",
        12,
        max_response_size,
    )

    assert result is None
    assert response.raw.bytes_read == max_response_size + 1
    assert response.closed is True


def test_extract_with_firecrawl_rejects_decompressed_provider_response_over_limit(
    monkeypatch,
):
    body = json.dumps(
        {
            "success": True,
            "data": {"markdown": "A" * 4096},
        }
    ).encode("utf-8")
    compressed = gzip.compress(body)
    max_response_size = len(compressed)
    assert len(body) > max_response_size
    response = _StreamingResponse(
        compressed,
        headers={"Content-Encoding": "gzip"},
    )
    _install_firecrawl_response(monkeypatch, response)

    result = extract_with_firecrawl(
        "https://example.com/article",
        "markdown",
        "configured-key",
        12,
        max_response_size,
    )

    assert result is None
    assert response.raw.bytes_read == len(compressed)
    assert response.closed is True


def test_web_fetcher_propagates_403_without_external_fallback(monkeypatch):
    firecrawl_calls = []

    def fake_fetch_url(*args, **kwargs):
        raise Exception("HTTP Error: 403 Forbidden")

    monkeypatch.setattr("opensprite.tools.web_fetch.fetch_url", fake_fetch_url)
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.extract_with_firecrawl",
        lambda *args, **kwargs: firecrawl_calls.append((args, kwargs)),
    )
    fetcher = WebFetcher(max_chars=500)

    with pytest.raises(Exception, match="HTTP Error: 403 Forbidden"):
        fetcher.fetch("https://example.com/blocked")

    assert firecrawl_calls == []


def test_web_fetcher_uses_configured_firecrawl_when_local_fetch_fails(monkeypatch):
    def fake_fetch_url(*args, **kwargs):
        raise Exception("HTTP Error: 403 Forbidden")

    calls = []
    callback_calls = []

    def fake_firecrawl(url, mode, api_key, timeout, max_response_size):
        calls.append((url, mode, api_key, timeout, max_response_size))
        return {
            "text": "Readable content from Firecrawl after local failure.",
            "extractor": "firecrawl",
            "title": "Fallback result",
            "finalUrl": "https://example.com/final",
            "status": 200,
        }

    monkeypatch.setattr("opensprite.tools.web_fetch.fetch_url", fake_fetch_url)
    monkeypatch.setattr("opensprite.tools.web_fetch.extract_with_firecrawl", fake_firecrawl)
    monkeypatch.setattr("opensprite.tools.web_fetch.socket.getaddrinfo", _public_getaddrinfo)

    result = WebFetcher(
        timeout=12,
        max_chars=500,
        max_response_size=2048,
        request_callback=lambda *args: callback_calls.append(args),
        firecrawl_api_key="configured-key",
    ).fetch("https://example.com/blocked")

    assert calls == [
        ("https://example.com/blocked", "markdown", "configured-key", 12, 2048)
    ]
    assert callback_calls == [("https://example.com/blocked", "markdown", 12)]
    assert result["extractor"] == "firecrawl"
    assert result["title"] == "Fallback result"
    assert result["finalUrl"] == "https://example.com/final"
    assert result["text"] == "Readable content from Firecrawl after local failure."


@pytest.mark.parametrize("firecrawl_outcome", ["empty", "error"])
def test_web_fetcher_preserves_local_error_when_firecrawl_fails(
    monkeypatch,
    firecrawl_outcome,
):
    local_error = RuntimeError("local transport failed")

    def fake_fetch_url(*args, **kwargs):
        raise local_error

    def fake_firecrawl(*args, **kwargs):
        if firecrawl_outcome == "error":
            raise RuntimeError("Firecrawl unavailable")
        return None

    monkeypatch.setattr("opensprite.tools.web_fetch.fetch_url", fake_fetch_url)
    monkeypatch.setattr("opensprite.tools.web_fetch.extract_with_firecrawl", fake_firecrawl)
    monkeypatch.setattr("opensprite.tools.web_fetch.socket.getaddrinfo", _public_getaddrinfo)

    with pytest.raises(RuntimeError) as error_info:
        WebFetcher(firecrawl_api_key="configured-key").fetch("https://example.com")

    assert error_info.value is local_error


def test_web_fetcher_rejects_private_target_before_callback_or_firecrawl(monkeypatch):
    firecrawl_calls = []
    callback_calls = []

    monkeypatch.setattr(
        "opensprite.tools.web_fetch.extract_with_firecrawl",
        lambda *args, **kwargs: firecrawl_calls.append((args, kwargs)),
    )

    with pytest.raises(Exception, match="blocked non-public IP address"):
        WebFetcher(
            request_callback=lambda *args: callback_calls.append(args),
            firecrawl_api_key="configured-key",
        ).fetch("http://127.0.0.1/private")

    assert callback_calls == []
    assert firecrawl_calls == []


def test_web_fetcher_rejects_private_redirect_without_firecrawl(monkeypatch):
    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return "http://127.0.0.1/private"

        def read(self, size=-1):
            return b"private"

    class FakeOpener:
        def open(self, *args, **kwargs):
            return FakeResponse()

    firecrawl_calls = []
    callback_calls = []
    monkeypatch.setattr("opensprite.tools.web_fetch.socket.getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.build_opener",
        lambda *args, **kwargs: FakeOpener(),
    )
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.extract_with_firecrawl",
        lambda *args, **kwargs: firecrawl_calls.append((args, kwargs)),
    )

    with pytest.raises(Exception, match="blocked non-public IP address"):
        WebFetcher(
            request_callback=lambda *args: callback_calls.append(args),
            firecrawl_api_key="configured-key",
        ).fetch("https://example.com/start")

    assert callback_calls == [("https://example.com/start", "markdown", 30)]
    assert firecrawl_calls == []


def test_web_fetcher_uses_configured_firecrawl_when_local_dns_fails(monkeypatch):
    def fake_validate_url(url):
        raise Exception("URL host could not be resolved: unavailable.example")

    firecrawl_calls = []
    callback_calls = []

    def fake_firecrawl(url, mode, api_key, timeout, max_response_size):
        firecrawl_calls.append(
            (url, mode, api_key, timeout, max_response_size)
        )
        return {
            "text": "Resolved by Firecrawl.",
            "extractor": "firecrawl",
            "title": "Remote fallback",
        }

    monkeypatch.setattr("opensprite.tools.web_fetch.validate_url", fake_validate_url)
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.fetch_url",
        lambda *args, **kwargs: pytest.fail("local fetch should not run after DNS failure"),
    )
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.extract_with_firecrawl",
        fake_firecrawl,
    )

    result = WebFetcher(
        max_response_size=2048,
        request_callback=lambda *args: callback_calls.append(args),
        firecrawl_api_key="configured-key",
    ).fetch("https://unavailable.example")

    assert firecrawl_calls == [
        ("https://unavailable.example", "markdown", "configured-key", 30, 2048)
    ]
    assert callback_calls == [("https://unavailable.example", "markdown", 30)]
    assert result["extractor"] == "firecrawl"
    assert result["text"] == "Resolved by Firecrawl."


def test_web_fetcher_keeps_short_locally_extracted_content(monkeypatch):
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.fetch_url",
        lambda *args, **kwargs: (
            "text/html",
            b"<html><title>Brief</title><body>Short</body></html>",
            200,
            "https://example.com/brief",
        ),
    )
    monkeypatch.setattr("opensprite.tools.web_fetch.html_to_markdown_turndown", lambda html: "Short")
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.extract_readability",
        lambda html, url: {"title": "", "content": ""},
    )
    firecrawl_calls = []
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.extract_with_firecrawl",
        lambda *args, **kwargs: firecrawl_calls.append((args, kwargs)),
    )

    result = WebFetcher(prefer_trafilatura=False).fetch("https://example.com/brief")

    assert result["extractor"] == "turndown"
    assert result["title"] == "Brief"
    assert result["text"] == "Short"
    assert firecrawl_calls == []


def test_web_fetcher_uses_explicitly_configured_firecrawl_for_short_content(monkeypatch):
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.fetch_url",
        lambda *args, **kwargs: (
            "text/html",
            b"<html><title>Brief</title><body>Short</body></html>",
            200,
            "https://example.com/brief",
        ),
    )
    monkeypatch.setattr("opensprite.tools.web_fetch.html_to_markdown_turndown", lambda html: "Short")
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.extract_readability",
        lambda html, url: {"title": "", "content": ""},
    )
    calls = []

    def fake_firecrawl(url, mode, api_key, timeout, max_response_size):
        calls.append((url, mode, api_key, timeout, max_response_size))
        return {
            "text": "Readable content from configured Firecrawl.",
            "extractor": "firecrawl",
            "title": "Readable fallback",
            "finalUrl": url,
        }

    monkeypatch.setattr("opensprite.tools.web_fetch.extract_with_firecrawl", fake_firecrawl)
    monkeypatch.setattr("opensprite.tools.web_fetch.socket.getaddrinfo", _public_getaddrinfo)

    result = WebFetcher(
        timeout=12,
        max_response_size=2048,
        prefer_trafilatura=False,
        firecrawl_api_key="configured-key",
    ).fetch("https://example.com/brief")

    assert calls == [
        ("https://example.com/brief", "markdown", "configured-key", 12, 2048)
    ]
    assert result["extractor"] == "firecrawl"
    assert result["title"] == "Readable fallback"
    assert result["text"] == "Readable content from configured Firecrawl."


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8765",
        "http://localhost",
        "http://10.0.0.1",
        "http://192.168.1.1",
        "http://172.16.0.1",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_validate_url_blocks_private_targets(url):
    with pytest.raises(Exception, match="blocked non-public IP address"):
        validate_url(url)


def test_validate_url_blocks_hosts_that_resolve_private(monkeypatch):
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    )

    with pytest.raises(Exception, match="blocked non-public IP address"):
        validate_url("https://example.com")


def test_web_fetcher_blocks_dns_rebinding_before_localhost_receives_request(
    monkeypatch,
):
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"private")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    dns_calls = 0

    def rebinding_getaddrinfo(host, port=None, *args, **kwargs):
        nonlocal dns_calls
        assert host == "rebind.example"
        dns_calls += 1
        address = "93.184.216.34" if dns_calls <= 2 else "127.0.0.1"
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, port),
            )
        ]

    monkeypatch.setattr(
        "opensprite.tools.web_fetch.socket.getaddrinfo",
        rebinding_getaddrinfo,
    )

    try:
        with pytest.raises(Exception, match="blocked non-public IP address"):
            WebFetcher(
                timeout=3,
                max_response_size=1024,
                prefer_trafilatura=False,
            ).fetch(f"http://rebind.example:{server.server_port}/secret")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert dns_calls == 3
    assert hits == []


def test_pinned_http_connection_preserves_original_host_header(monkeypatch):
    host_headers = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host_headers.append(self.headers["Host"])
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        web_fetch_module,
        "_resolve_public_endpoints",
        lambda host, port=None: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", port),
            )
        ],
    )

    try:
        content_type, content, status, final_url = fetch_url(
            f"http://public.example:{server.server_port}/article",
            timeout=3,
            max_response_size=1024,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert host_headers == [f"public.example:{server.server_port}"]
    assert (content_type, content, status) == ("text/plain", b"ok", 200)
    assert final_url == f"http://public.example:{server.server_port}/article"


def test_pinned_https_connection_preserves_original_tls_sni(monkeypatch):
    raw_socket = object()
    wrapped_socket = object()
    wrap_calls = []

    class FakeContext:
        check_hostname = True

        def wrap_socket(self, sock, *, server_hostname):
            wrap_calls.append((sock, server_hostname))
            return wrapped_socket

    monkeypatch.setattr(
        web_fetch_module,
        "_connect_verified_socket",
        lambda *args, **kwargs: raw_socket,
    )
    connection = object.__new__(web_fetch_module._PinnedHTTPSConnection)
    connection.host = "public.example"
    connection.port = 443
    connection.timeout = 3
    connection.source_address = None
    connection._tunnel_host = None
    connection._context = FakeContext()

    connection.connect()

    assert wrap_calls == [(raw_socket, "public.example")]
    assert connection.sock is wrapped_socket


def test_verified_socket_connects_to_exact_ipv6_sockaddr(monkeypatch):
    ipv6_sockaddr = ("2001:4860:4860::8888", 443, 0, 7)
    created = []

    class FakeSocket:
        def __init__(self, family, socktype, proto):
            self.family = family
            self.socktype = socktype
            self.proto = proto
            self.timeout = None
            self.connected_to = None
            created.append(self)

        def settimeout(self, timeout):
            self.timeout = timeout

        def connect(self, sockaddr):
            self.connected_to = sockaddr

        def close(self):
            pass

    monkeypatch.setattr(
        web_fetch_module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ipv6_sockaddr,
            )
        ],
    )
    monkeypatch.setattr(web_fetch_module.socket, "socket", FakeSocket)

    connected = web_fetch_module._connect_verified_socket(
        "public-v6.example",
        443,
        4,
    )

    assert connected is created[0]
    assert created[0].family == socket.AF_INET6
    assert created[0].timeout == 4
    assert created[0].connected_to == ipv6_sockaddr


def test_safe_redirect_revalidates_hop_and_keeps_urllib_post_semantics(
    monkeypatch,
):
    validated = []
    target = "https://redirected.example/next"
    monkeypatch.setattr(
        web_fetch_module,
        "validate_url",
        lambda url: validated.append(url) or True,
    )
    request = web_fetch_module.Request(
        "https://origin.example/start",
        data=b"payload",
        headers={
            "Content-Type": "application/json",
            "Content-Length": "7",
        },
        method="POST",
    )

    redirected = web_fetch_module._SafeRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        target,
    )

    assert validated == [target]
    assert redirected.full_url == target
    assert redirected.get_method() == "GET"
    assert redirected.data is None
    assert redirected.get_header("Content-type") is None
    assert redirected.get_header("Content-length") is None


def test_do_fetch_blocks_private_final_url(monkeypatch):
    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return "http://127.0.0.1/private"

        def read(self, size=-1):
            return b"ok"

    class FakeOpener:
        def open(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("opensprite.tools.web_fetch.socket.getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr("opensprite.tools.web_fetch.build_opener", lambda *args, **kwargs: FakeOpener())

    with pytest.raises(Exception, match="blocked non-public IP address"):
        _do_fetch("https://example.com", 30, "test-agent", 1024)


def test_do_fetch_stops_reading_when_response_exceeds_limit(monkeypatch):
    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def __init__(self):
            self.reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return "https://example.com/large"

        def read(self, size=-1):
            self.reads += 1
            return b"abc" if self.reads == 1 else b"def"

    class FakeOpener:
        def open(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("opensprite.tools.web_fetch.socket.getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr("opensprite.tools.web_fetch.build_opener", lambda *args, **kwargs: FakeOpener())

    with pytest.raises(Exception, match="exceeds 5 bytes limit"):
        _do_fetch("https://example.com/large", 30, "test-agent", 5)


def test_do_fetch_decompresses_gzip_response(monkeypatch):
    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8", "Content-Encoding": "gzip"}

        def __init__(self):
            self._content = gzip.compress(b"<html><body>Readable quote page</body></html>")
            self._read = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return "https://example.com/quote"

        def read(self, size=-1):
            if self._read:
                return b""
            self._read = True
            return self._content

    class FakeOpener:
        def open(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("opensprite.tools.web_fetch.socket.getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr("opensprite.tools.web_fetch.build_opener", lambda *args, **kwargs: FakeOpener())

    content, status, headers, final_url = _do_fetch("https://example.com/quote", 30, "test-agent", 1024)

    assert content == b"<html><body>Readable quote page</body></html>"
    assert status == 200
    assert headers["Content-Encoding"] == "gzip"
    assert final_url == "https://example.com/quote"


def test_fetch_url_handles_lowercase_content_headers(monkeypatch):
    class FakeResponse:
        status = 200
        headers = {
            "content-type": "application/json",
            "content-encoding": "deflate",
        }

        def __init__(self):
            self._content = zlib.compress(b'{"ok": true}')
            self._read = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return "https://example.com/data"

        def read(self, size=-1):
            if self._read:
                return b""
            self._read = True
            return self._content

    class FakeOpener:
        def open(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "opensprite.tools.web_fetch.socket.getaddrinfo",
        _public_getaddrinfo,
    )
    monkeypatch.setattr(
        "opensprite.tools.web_fetch.build_opener",
        lambda *args, **kwargs: FakeOpener(),
    )

    content_type, content, status, final_url = fetch_url(
        "https://example.com/data",
        timeout=30,
        max_response_size=1024,
    )

    assert content_type == "application/json"
    assert content == b'{"ok": true}'
    assert status == 200
    assert final_url == "https://example.com/data"


@pytest.mark.parametrize(
    ("encoding", "compress"),
    [
        ("gzip", gzip.compress),
        ("deflate", zlib.compress),
    ],
)
def test_decode_response_body_decompresses_within_limit(encoding, compress):
    content = b"Readable response body"

    assert _decode_response_body(
        compress(content),
        {"Content-Encoding": encoding},
        len(content),
    ) == content


@pytest.mark.parametrize(
    ("encoding", "compress"),
    [
        ("gzip", gzip.compress),
        ("deflate", zlib.compress),
    ],
)
def test_decode_response_body_rejects_decompressed_content_over_limit(
    encoding,
    compress,
):
    max_response_size = 64
    compressed = compress(b"A" * 4096)
    assert len(compressed) <= max_response_size

    with pytest.raises(Exception, match="Decompressed response too large.*64 bytes limit"):
        _decode_response_body(
            compressed,
            {"Content-Encoding": encoding},
            max_response_size,
        )
