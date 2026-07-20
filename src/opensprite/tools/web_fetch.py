#!/usr/bin/env python3
"""
WebFetch - 網頁內容擷取工具 (v5.2 (Firecrawl))

==========================================
使用說明 Usage Instructions
==========================================

## 安裝 Installation

```bash
# 建議安裝 trafilatura (更強的擷取能力)
pip install trafilatura

# html2text 用於 Markdown 轉換
pip install html2text

# Firecrawl (付費服務，可選)
pip install httpx

# 或使用 --break-system-packages (如需要)
pip install trafilatura html2text httpx --break-system-packages
```

==========================================
## Python 模組使用方式
==========================================

### 最簡單用法 (推薦)
```python
from web_fetch import fetch

# 一行就夠了！所有功能自動處理
result = fetch("https://example.com")

print(result['text'])  # 擷取的內容
```

**自動處理的事：**
- ✅ URL 驗證 (必須 http/https)
- ✅ 優先使用 trafilatura 擷取
- ✅ 可選 Firecrawl (付費服務，需 API Key)
- ✅ 失敗時自動用 turndown (html2text)
- ✅ 圖片自動回傳 base64
- ✅ 5MB 大小限制
- ✅ 30 秒超時

### 回傳格式
```python
result = {
    'url': 'https://example.com',      # 原始 URL
    'status': 200,                      # HTTP 狀態碼
    'contentType': 'text/html',         # 內容類型
    'title': 'Example Domain',          # 頁面標題
    'extractor': 'trafilatura',         # 擷取器: trafilatura | firecrawl | turndown | readability
    'text': '...',                      # 擷取的內容
    'truncated': False,                 # 是否被截斷
    'is_image': False,                  # 是否為圖片
    'attachments': None,                # 圖片附件 (base64)
}
```

### 進階用法
```python
from web_fetch import WebFetcher

# 自訂參數
fetcher = WebFetcher(
    max_chars=50000,        # 最大字數 (預設 50000)
    timeout=30,             # 請求超時秒數 (預設 30)
    prefer_trafilatura=True # 優先使用 trafilatura (預設 True)
)

# 擷取並指定輸出模式
result = fetcher.fetch("https://example.com", mode="markdown")  # 或 "text"

# 或使用便捷函式
from web_fetch import fetch
result = fetch(url, max_chars=10000)
```

### 參數說明

| 參數 | 類型 | 預設 | 說明 |
|------|------|------|------|
| url | str | 必填 | 要擷取的網址 |
| max_chars | int | 50000 | 最大字數限制 |
| timeout | int | 30 | 請求超時(秒) |
| mode | str | "markdown" | 輸出模式: "markdown" 或 "text" |

### 回傳格式

```python
{
    'url': str,           # 原始 URL
    'finalUrl': str,      # 最終 URL (含重導向)
    'status': int,        # HTTP 狀態碼
    'contentType': str,   # Content-Type
    'title': str|None,    # 頁面標題
    'extractor': str,     # 擷取器類型:
                          #   'trafilatura' - 專業級擷取
                          #   'turndown' - HTML 轉 Markdown
                          #   'readability' - 簡易版擷取
                          #   'json' - JSON 解析
                          #   'raw' - 原始內容
    'text': str,          # 擷取的內容
    'truncated': bool     # 是否被截斷
}
```

==========================================
## 命令列使用方式
==========================================

```bash
# 基本用法
python web_fetch.py https://example.com

# 指定最大字數
python web_fetch.py https://example.com --max-chars 5000

# 輸出純文字
python web_fetch.py https://example.com --mode text

# 組合使用
python web_fetch.py https://example.com --max-chars 3000 --mode markdown
```

### 命令列參數

| 參數 | 說明 |
|------|------|
| url | 要擷取的網址 (必填) |
| --max-chars N | 最大字數 (預設 50000) |
| --mode format | 輸出模式: markdown 或 text (預設 markdown) |

==========================================
## 擷取器說明 (優先順序)
==========================================

1. **Trafilatura** - 專業級網頁文章擷取
   - 自動去除廣告、導航、側邊欄
   - 支援中英文
   - 適合: 新聞、部落格、文章

2. **Turndown (html2text)** - HTML 轉 Markdown
   - 類似 opencode 的 turndown 套件
   - 保留標題、連結、列表、程式碼區塊
   - 適合: 當 trafilatura 失敗時

3. **Readability** - 簡易版擷取
   - 當 turndown 也失敗時使用
   - 適合: 簡單的 HTML 頁面

==========================================
## 安裝需求
==========================================

- Python 3.7+

```bash
pip install trafilatura html2text
```

==========================================
"""

import json
import ipaddress
import re
import socket
import asyncio
import gzip
import io
import zlib
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)
from urllib.error import URLError, HTTPError
from html import unescape

import httpx

from .base import Tool
from .validation import NON_EMPTY_STRING_PATTERN
from .web_blocking import looks_blocked_or_challenge

WEB_FETCH_MIN_CONTENT_CHARS = 800


# 嘗試引入 trafilatura
try:
    from trafilatura import extract as trafilatura_extract
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

# 嘗試引入 html2text (Turndown 風格)
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False


# ============================================
# Turndown 風格 HTML 轉 Markdown
# ============================================

def html_to_markdown_turndown(html: str) -> str:
    """使用 html2text 將 HTML 轉換為 Markdown (類似 turndown)"""
    if not HTML2TEXT_AVAILABLE:
        return simple_html_to_markdown(html)
    
    try:
        h = html2text.HTML2Text()
        h.body_width = 0  # 不斷行
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.ignore_tables = False
        h.single_line_break = True
        h.wrap_links = False
        h.wrap_lists = True
        
        markdown = h.handle(html)
        
        # 清理多餘空白
        markdown = re.sub(r'\n{4,}', '\n\n\n', markdown)
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        return markdown.strip()
    except Exception:
        return simple_html_to_markdown(html)


def extract_text_from_html(html: str) -> str:
    """使用類似 opencode HTMLRewriter 的方式提取純文字"""
    # 移除 script, style, noscript, iframe, object, embed
    text = re.sub(r'<(script|style|noscript|iframe|object|embed)[^>]*>[\s\S]*?</\1>', '', html, flags=re.IGNORECASE)
    
    # 移除所有 HTML 標籤
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 處理實體
    text = unescape(text)
    
    # 清理空白
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()


def simple_html_to_markdown(html: str) -> str:
    """簡單的 HTML 轉 Markdown (當 html2text 不可用時)"""
    # 標題
    for i in range(6, 0, -1):
        html = re.sub(rf'<h{i}[^>]*>([\s\S]*?)</h{i}>', f"#{'#'*i} \\1\n", html, flags=re.IGNORECASE)
    
    # 連結
    html = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', r'[\2](\1)', html)
    
    # 圖片
    html = re.sub(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>', r'![](\1)', html)
    
    # 粗體
    html = re.sub(r'<strong[^>]*>([\s\S]*?)</strong>', r'**\1**', html)
    html = re.sub(r'<b[^>]*>([\s\S]*?)</b>', r'**\1**', html)
    
    # 斜體
    html = re.sub(r'<em[^>]*>([\s\S]*?)</em>', r'*\1*', html)
    html = re.sub(r'<i[^>]*>([\s\S]*?)</i>', r'*\1*', html)
    
    # 程式碼
    html = re.sub(r'<code[^>]*>([\s\S]*?)</code>', r'`\1`', html)
    html = re.sub(r'<pre[^>]*>([\s\S]*?)</pre>', r'```\n\1\n```', html)
    
    # 列表
    html = re.sub(r'<li[^>]*>([\s\S]*?)</li>', r'\n- \1', html)
    html = re.sub(r'<ul[^>]*>', '', html)
    html = re.sub(r'</ul>', '', html)
    
    # 段落
    html = re.sub(r'</p>', '\n\n', html)
    html = re.sub(r'<p[^>]*>', '', html)
    
    # 移除多餘標籤
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'<hr\s*/?>', '\n---\n', html)
    
    # 移除所有剩餘標籤
    html = re.sub(r'<[^>]+>', '', html)
    
    # 實體
    html = unescape(html)
    
    # 清理
    html = re.sub(r'\n{3,}', '\n\n', html)
    
    return html.strip()


# ============================================
# 簡易 Readability (當所有方法失敗時)
# ============================================

class SimpleReadability:
    REMOVE_TAGS = {'script', 'style', 'nav', 'header', 'footer', 'aside',
                   'form', 'iframe', 'noscript', 'svg', 'button', 'input'}
    
    def __init__(self, html: str, url: str = ""):
        self.html = html
        self.url = url
        self.title = self._extract_title()
        
    def _extract_title(self) -> str:
        match = re.search(r'<title[^>]*>([\s\S]*?)</title>', self.html, re.IGNORECASE)
        return self._clean_text(match.group(1)) if match else ""
    
    def _clean_text(self, text: str) -> str:
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _remove_tags(self, html: str) -> str:
        html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
        for tag in self.REMOVE_TAGS:
            html = re.sub(rf'<{tag}[^>]*>[\s\S]*?</{tag}>', '', html, flags=re.IGNORECASE)
        return html
    
    def parse(self) -> dict:
        html = self._remove_tags(self.html)
        best_score, best_content = 0, ""
        
        content_tags = re.findall(
            r'<(article|main|section|div|p|td|th|li)[^>]*>([\s\S]*?)</\1>',
            html, re.IGNORECASE
        )
        
        for tag, content in content_tags:
            text = re.sub(r'<[^>]+>', '', content)
            text = self._clean_text(text)
            if len(text) < 50:
                continue
            
            score = min(len(text) / 100, 10)
            if tag in ('article', 'main'):
                score += 25
            if score > best_score:
                best_score, best_content = score, text
        
        if not best_content:
            body_match = re.search(r'<body[^>]*>([\s\S]*?)</body>', html, re.IGNORECASE)
            if body_match:
                best_content = self._clean_text(re.sub(r'<[^>]+>', '', body_match.group(1)))
        
        return {'title': self.title, 'content': best_content}


def extract_readability(html: str, url: str = "") -> dict:
    try:
        return SimpleReadability(html, url).parse()
    except Exception as e:
        return {'title': '', 'content': '', 'error': str(e)}


# ============================================
# 網頁擷取核心
# ============================================

# 預設 User-Agent
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

def _blocked_ip_reason(value: str) -> str | None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if address.is_global:
        return None
    return f"blocked non-public IP address: {address}"


def _resolve_public_endpoints(
    host: str,
    port: int | None = None,
) -> list[tuple[int, int, int, str, tuple]]:
    """Resolve a host once and return only endpoints safe to connect to."""
    reason = _blocked_ip_reason(host)
    if reason:
        raise Exception(reason)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise Exception(f"URL host could not be resolved: {host}") from exc
    for info in infos:
        address = info[4][0]
        reason = _blocked_ip_reason(address)
        if reason:
            raise Exception(reason)
    if not infos:
        raise Exception(f"URL host could not be resolved: {host}")
    return infos


def _validate_public_host(host: str, port: int | None = None) -> None:
    _resolve_public_endpoints(host, port)


def _connect_verified_socket(
    host: str,
    port: int,
    timeout: float | object,
    source_address: tuple[str, int] | None = None,
):
    """Connect to the exact public sockaddr returned by the validated lookup."""
    endpoints = _resolve_public_endpoints(host, port)
    last_error: OSError | None = None
    for family, socktype, proto, _canonname, sockaddr in endpoints:
        connection = None
        try:
            connection = socket.socket(family, socktype, proto)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                connection.settimeout(timeout)
            if source_address:
                connection.bind(source_address)
            connection.connect(sockaddr)
            return connection
        except OSError as exc:
            last_error = exc
            if connection is not None:
                connection.close()
    if last_error is not None:
        raise last_error
    raise OSError(f"Could not connect to validated host: {host}")


def validate_url(url: str) -> bool:
    """Validate URL scheme and block private/internal network targets."""
    if not url:
        raise Exception("URL is required")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise Exception("URL must start with http:// or https://")
    if not parsed.hostname:
        raise Exception("URL host is required")
    _validate_public_host(parsed.hostname, parsed.port)
    return True


def _read_response_with_limit(response, max_response_size: int) -> bytes:
    if max_response_size < 1:
        raise ValueError("max_response_size must be at least 1")

    chunks: list[bytes] = []
    total = 0
    while True:
        read_size = min(64 * 1024, max_response_size - total + 1)
        chunk = response.read(read_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_response_size:
            raise Exception(f"Response too large (exceeds {max_response_size} bytes limit)")
        chunks.append(chunk)
    return b"".join(chunks)


def _decompressed_response_too_large(max_response_size: int) -> Exception:
    return Exception(
        f"Decompressed response too large (exceeds {max_response_size} bytes limit)"
    )


def _get_header(headers, name: str, default: str = "") -> str:
    """Read a HTTP header without depending on the sender's casing."""
    value = headers.get(name) if hasattr(headers, "get") else None
    if value is not None:
        return str(value)
    if hasattr(headers, "items"):
        expected = name.casefold()
        for key, candidate in headers.items():
            if str(key).casefold() == expected:
                return str(candidate)
    return default


def _decode_response_body(
    content: bytes,
    headers: dict[str, str],
    max_response_size: int,
) -> bytes:
    encoding = _get_header(headers, "Content-Encoding").strip().lower()
    if encoding == "gzip" or content.startswith(b"\x1f\x8b"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
                decoded = stream.read(max_response_size + 1)
        except (OSError, EOFError):
            return content
        if len(decoded) > max_response_size:
            raise _decompressed_response_too_large(max_response_size)
        return decoded
    if encoding == "deflate":
        try:
            decompressor = zlib.decompressobj()
            decoded = decompressor.decompress(content, max_response_size + 1)
            if len(decoded) > max_response_size or decompressor.unconsumed_tail:
                raise _decompressed_response_too_large(max_response_size)
            decoded += decompressor.flush(max_response_size + 1 - len(decoded))
        except zlib.error:
            return content
        if len(decoded) > max_response_size:
            raise _decompressed_response_too_large(max_response_size)
        return decoded
    return content


class _PinnedHTTPConnection(HTTPConnection):
    """HTTP connection whose socket is pinned to its validated DNS answer."""

    def connect(self) -> None:
        self.sock = _connect_verified_socket(
            self.host,
            self.port,
            self.timeout,
            self.source_address,
        )
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(HTTPSConnection):
    """HTTPS connection pinned to a public IP while retaining hostname SNI."""

    def connect(self) -> None:
        server_hostname = self._tunnel_host or self.host
        self.sock = _connect_verified_socket(
            self.host,
            self.port,
            self.timeout,
            self.source_address,
        )
        if self._tunnel_host:
            self._tunnel()
        self.sock = self._context.wrap_socket(
            self.sock,
            server_hostname=server_hostname,
        )


class _PinnedHTTPHandler(HTTPHandler):
    def http_open(self, req):
        return self.do_open(_PinnedHTTPConnection, req)


class _PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(
            _PinnedHTTPSConnection,
            req,
            context=self._context,
        )


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url: str, timeout: int = 30, max_response_size: int = 5 * 1024 * 1024) -> tuple:
    """Fetch one public URL without hidden provider or access-control retries."""
    content, status, headers, final_url = _do_fetch(url, timeout, DEFAULT_UA, max_response_size)
    return _get_header(headers, 'Content-Type', 'text/html'), content, status, final_url


def _do_fetch(url: str, timeout: int, user_agent: str, max_response_size: int) -> tuple:
    """執行實際的 HTTP 請求"""
    validate_url(url)
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/markdown;q=1.0, text/x-markdown;q=0.9, text/plain;q=0.8, text/html;q=0.7, */*;q=0.1',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    request = Request(url, headers=headers)
    opener = build_opener(
        ProxyHandler({}),
        _PinnedHTTPHandler(),
        _PinnedHTTPSHandler(),
        _SafeRedirectHandler(),
    )
    
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
            validate_url(final_url)
            headers = dict(response.headers)
            content = _read_response_with_limit(response, max_response_size)
            return (
                _decode_response_body(content, headers, max_response_size),
                response.status,
                headers,
                final_url,
            )
    except HTTPError as e:
        raise Exception(f"HTTP Error: {e.code} {e.reason}")
    except URLError as e:
        raise Exception(f"URL Error: {e.reason}")


def decode_content(content: bytes, content_type: str) -> str:
    charset = 'utf-8'
    if 'charset=' in content_type:
        charset = content_type.split('charset=')[-1].split(';')[0].strip()
    try:
        return content.decode(charset)
    except UnicodeDecodeError:
        return content.decode('utf-8', errors='replace')


def truncate_text(text: str, max_chars: int) -> tuple:
    return (text, False) if len(text) <= max_chars else (text[:max_chars], True)


# ============================================
# Trafilatura 擷取
# ============================================

def extract_with_trafilatura(html: str, mode: str = 'markdown') -> dict:
    if not TRAFILATURA_AVAILABLE:
        return None
    
    try:
        downloaded = html
        if not downloaded:
            return None
        
        output_format = 'markdown' if mode == 'markdown' else 'text'
        text = trafilatura_extract(downloaded, output_format=output_format)
        
        if text:
            title = None
            try:
                meta = trafilatura_extract(downloaded, output_format='json')
                if meta:
                    meta_obj = json.loads(meta)
                    title = meta_obj.get('title')
            except:
                pass
            
            return {'text': text, 'extractor': 'trafilatura', 'title': title}
    except Exception:
        pass
    
    return None


# ============================================
# Firecrawl 擷取 (付費服務)
# ============================================

DEFAULT_FIRECRAWL_BASE_URL = "https://api.firecrawl.dev"


def _read_stream_with_limit(chunks, max_response_size: int) -> bytes:
    if max_response_size < 1:
        raise ValueError("max_response_size must be at least 1")
    content: list[bytes] = []
    total = 0
    for chunk in chunks:
        total += len(chunk)
        if total > max_response_size:
            raise Exception(
                f"Response too large (exceeds {max_response_size} bytes limit)"
            )
        content.append(chunk)
    return b"".join(content)


def extract_with_firecrawl(url: str, mode: str = 'markdown',
                           api_key: str = None,
                           timeout: int = 30,
                           max_response_size: int = 5 * 1024 * 1024) -> dict:
    """使用 Firecrawl API 擷取網頁
    
    參數:
        url: 要擷取的網址
        mode: 輸出模式 (markdown/text)
        api_key: Firecrawl API Key
        timeout: 超時秒數
    
    需要:
        httpx is included in the core OpenSprite dependencies
        Firecrawl API Key: https://firecrawl.dev
    """
    if not api_key:
        # 嘗試從環境變數取得
        import os
        api_key = os.environ.get('FIRECRAWL_API_KEY')
    
    if not api_key:
        return None
    
    try:
        endpoint = f"{DEFAULT_FIRECRAWL_BASE_URL}/v2/scrape"
        
        body = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
            "timeout": timeout * 1000,
        }
        
        with httpx.stream(
            "POST",
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
            },
            json=body,
            timeout=timeout,
        ) as response:
            if not response.is_success:
                return None

            raw_content = _read_stream_with_limit(
                response.iter_raw(
                    chunk_size=min(64 * 1024, max_response_size + 1)
                ),
                max_response_size,
            )
            content = _decode_response_body(
                raw_content,
                response.headers,
                max_response_size,
            )
            payload = json.loads(content.decode(response.encoding or "utf-8"))
        
        if not payload.get('success'):
            return None
        
        data = payload.get('data', {})
        raw_text = data.get('markdown') or data.get('content') or ""
        
        if not raw_text:
            return None
        
        # 轉換為純文字如果需要
        if mode == 'text':
            import re
            # 簡單的 Markdown 轉文字
            text = re.sub(r'#+ ', '', raw_text)  # 標題
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # 連結
            text = re.sub(r'[*_`]+', '', text)  # 強調
            text = re.sub(r'\n{3,}', '\n\n', text)  # 多餘空行
            raw_text = text.strip()
        
        metadata = data.get('metadata', {})
        
        return {
            'text': raw_text,
            'extractor': 'firecrawl',
            'title': metadata.get('title'),
            'finalUrl': metadata.get('sourceURL'),
            'status': metadata.get('statusCode'),
        }
    
    except Exception:
        pass
    
    return None


# ============================================
# 主類別
# ============================================

class WebFetcher:
    """網頁擷取器 (參考 OpenCode)"""
    
    # 圖片類型 (不包含 SVG 和特定類型)
    IMAGE_EXCLUDE = {'image/svg+xml', 'image/vnd.fastbidsheet'}
    DEFAULT_MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB
    
    def __init__(self, max_chars: int = 50000, timeout: int = 30, 
                 max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
                 prefer_trafilatura: bool = True,
                 request_callback: callable = None,  # 權限詢問回調
                 firecrawl_api_key: str = None):       # Firecrawl API Key
        self.max_chars = max_chars
        self.max_response_size = max_response_size
        self.timeout = timeout
        self.prefer_trafilatura = prefer_trafilatura and TRAFILATURA_AVAILABLE
        self.request_callback = request_callback
        self.firecrawl_api_key = firecrawl_api_key

    def _firecrawl_fallback(self, url: str, mode: str) -> dict | None:
        if not self.firecrawl_api_key:
            return None
        try:
            firecrawl_result = extract_with_firecrawl(
                url,
                mode,
                self.firecrawl_api_key,
                self.timeout,
                self.max_response_size,
            )
        except Exception:
            return None
        if not isinstance(firecrawl_result, dict) or not firecrawl_result.get('text'):
            return None

        text, truncated = truncate_text(str(firecrawl_result['text']), self.max_chars)
        return {
            'url': url,
            'finalUrl': firecrawl_result.get('finalUrl') or url,
            'status': firecrawl_result.get('status') or 200,
            'contentType': 'text/plain' if mode == 'text' else 'text/markdown',
            'extractor': 'firecrawl',
            'title': firecrawl_result.get('title') or url,
            'text': text,
            'truncated': truncated,
            'attachments': None,
            'is_image': False,
        }

    @staticmethod
    def _allows_external_fallback(error: Exception) -> bool:
        message = str(error)
        return not any(
            marker in message
            for marker in (
                "URL is required",
                "URL must start with",
                "URL host is required",
                "blocked non-public IP address",
            )
        )
    
    def fetch(self, url: str, mode: str = 'markdown') -> dict:
        # URL 驗證 (參考 OpenCode)
        try:
            validate_url(url)
        except Exception as error:
            if (
                "URL host could not be resolved:" in str(error)
                and self.firecrawl_api_key
            ):
                if self.request_callback:
                    self.request_callback(url, mode, self.timeout)
                firecrawl_result = self._firecrawl_fallback(url, mode)
                if firecrawl_result:
                    return firecrawl_result
            raise
        
        # 權限詢問回調 (參考 OpenCode ctx.ask)
        if self.request_callback:
            self.request_callback(url, mode, self.timeout)
        try:
            content_type, content, status, final_url = fetch_url(
                url,
                self.timeout,
                self.max_response_size,
            )
        except Exception as error:
            if self._allows_external_fallback(error):
                firecrawl_result = self._firecrawl_fallback(url, mode)
                if firecrawl_result:
                    return firecrawl_result
            raise

        result = {
            'url': url, 'finalUrl': final_url, 'status': status,
            'contentType': content_type, 'extractor': 'raw',
            'title': f"{url} ({content_type})",
            'text': '', 'truncated': False,
            'attachments': None,  # 圖片附件
            'is_image': False
        }
        
        content_type_lower = content_type.lower()
        
        # 圖片處理 (參考 OpenCode)
        mime = content_type.split(';')[0].strip().lower() if ';' in content_type else content_type.strip().lower()
        is_image = mime.startswith('image/') and mime not in self.IMAGE_EXCLUDE
        
        if is_image:
            import base64
            base64_content = base64.b64encode(content).decode('utf-8')
            result['is_image'] = True
            result['extractor'] = 'image'
            result['text'] = 'Image fetched successfully'
            result['attachments'] = [{
                'type': 'file',
                'mime': mime,
                'url': f'data:{mime};base64,{base64_content}'
            }]
            return result
        
        text = decode_content(content, content_type)
        
        # JSON 處理
        if 'application/json' in content_type_lower:
            try:
                json_data = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
                result['text'], result['truncated'] = truncate_text(json_data, self.max_chars)
                result['extractor'] = 'json'
            except:
                result['text'], result['truncated'] = truncate_text(text, self.max_chars)
        
        # HTML 處理
        elif 'text/html' in content_type_lower:
            extractor_used = None
            
            # 1. 優先嘗試 trafilatura
            if self.prefer_trafilatura:
                trafilatura_result = extract_with_trafilatura(text, mode)
                if trafilatura_result and trafilatura_result.get('text'):
                    result['text'] = trafilatura_result['text']
                    result['extractor'] = trafilatura_result['extractor']
                    result['title'] = trafilatura_result.get('title')
                    extractor_used = 'trafilatura'
            
            # 2. 如果 trafilatura 失敗，使用 Turndown (html2text)
            if not extractor_used:
                if mode == 'text':
                    # 純文字模式
                    result['text'] = extract_text_from_html(text)
                    result['extractor'] = 'turndown'
                else:
                    # Markdown 模式 (使用 html2text)
                    result['text'] = html_to_markdown_turndown(text)
                    result['extractor'] = 'turndown'
                
                # 取得標題
                title_match = re.search(r'<title[^>]*>([\s\S]*?)</title>', text, re.IGNORECASE)
                if title_match:
                    result['title'] = unescape(title_match.group(1)).strip()
            
            # 3. 如果也失敗，使用簡易 Readability
            if not result['text'] or len(result['text']) < 50:
                readability_result = extract_readability(text, url)
                if readability_result.get('content'):
                    result['title'] = readability_result.get('title')
                    result['text'] = readability_result['content']
                    result['extractor'] = 'readability'
            
            # 4. 如果本機擷取不足，且已明確設定 API Key，使用 Firecrawl
            if (not result['text'] or len(result['text']) < 50) and self.firecrawl_api_key:
                firecrawl_result = self._firecrawl_fallback(url, mode)
                if firecrawl_result:
                    result.update(firecrawl_result)
            
            result['text'], result['truncated'] = truncate_text(result['text'], self.max_chars)
        
        else:
            result['text'], result['truncated'] = truncate_text(text, self.max_chars)

        return result


class WebFetchTool(Tool):
    """Tool-compatible wrapper around WebFetcher."""

    def __init__(
        self,
        max_chars: int = 50000,
        max_response_size: int = WebFetcher.DEFAULT_MAX_RESPONSE_SIZE,
        timeout: int = 30,
        prefer_trafilatura: bool = True,
        firecrawl_api_key: str | None = None,
    ):
        self.fetcher = WebFetcher(
            max_chars=max_chars,
            max_response_size=max_response_size,
            timeout=timeout,
            prefer_trafilatura=prefer_trafilatura,
            firecrawl_api_key=firecrawl_api_key,
        )

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch and extract readable content from a URL. Prefer this after selecting a specific source from web_search."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch", "pattern": NON_EMPTY_STRING_PATTERN},
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters to return",
                    "default": self.fetcher.max_chars,
                    "minimum": 1,
                },
            },
            "required": ["url"],
        }

    async def _execute(self, url: str, max_chars: int | None = None, **kwargs) -> str:
        effective_max_chars = max_chars if max_chars is not None else self.fetcher.max_chars
        fetcher = WebFetcher(
            max_chars=effective_max_chars,
            max_response_size=self.fetcher.max_response_size,
            timeout=self.fetcher.timeout,
            prefer_trafilatura=self.fetcher.prefer_trafilatura,
            firecrawl_api_key=self.fetcher.firecrawl_api_key,
        )
        result = await asyncio.to_thread(fetcher.fetch, url)
        content = str(result.get("text") or "")
        content_chars = len(content.strip())
        raw_status = result.get("status")
        try:
            status = int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            status = None
        title = str(result.get("title") or "")
        blocked_or_challenge = looks_blocked_or_challenge(title=title, content=content, status=status)
        is_too_short = content_chars < WEB_FETCH_MIN_CONTENT_CHARS
        has_main_content = bool(content.strip()) and not is_too_short and not blocked_or_challenge
        return json.dumps(
            {
                "type": "web_fetch",
                "query": url,
                "url": result.get("url"),
                "final_url": result.get("finalUrl"),
                "title": result.get("title"),
                "content": content,
                "summary": result.get("title") or result.get("url") or url,
                "provider": "web_fetch",
                "extractor": result.get("extractor"),
                "status": result.get("status"),
                "content_type": result.get("contentType"),
                "truncated": result.get("truncated"),
                "content_chars": content_chars,
                "has_title": bool(str(result.get("title") or "").strip()),
                "has_main_content": has_main_content,
                "is_too_short": is_too_short,
                "blocked_or_challenge": blocked_or_challenge,
                "min_content_chars": WEB_FETCH_MIN_CONTENT_CHARS,
                "items": [],
            },
            ensure_ascii=False,
        )


# ============================================
# 便捷函式
# ============================================

def fetch(url: str, max_chars: int = 50000, timeout: int = 30,
          max_response_size: int = WebFetcher.DEFAULT_MAX_RESPONSE_SIZE,
          request_callback: callable = None,
          firecrawl_api_key: str = None) -> dict:
    """快速擷取網頁
    
    參數:
        url: 網址
        max_chars: 最大字數
        timeout: 超時秒數
        max_response_size: 最大 HTTP 回應大小（bytes）
        request_callback: 權限詢問回調 (url, mode, timeout) -> None
        firecrawl_api_key: Firecrawl API Key (可選，付費服務)
    """
    return WebFetcher(
        max_chars=max_chars, 
        max_response_size=max_response_size,
        timeout=timeout,
        request_callback=request_callback,
        firecrawl_api_key=firecrawl_api_key
    ).fetch(url)


