"""SearXNG endpoint and bounded-response helpers."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit


_SEARXNG_ENDPOINT_PATHS = ("/search", "/config")
SEARXNG_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _validated_http_url(value: str, *, label: str) -> tuple[str, SplitResult]:
    normalized = str(value or "").strip()
    try:
        parsed = urlsplit(normalized)
        # Accessing port performs range and syntax validation.
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(f"{label} must be an absolute HTTP(S) URL with a hostname") from exc

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError(f"{label} must be an absolute HTTP(S) URL with a hostname")
    return normalized, parsed


def normalize_searxng_proxy_url(proxy_url: str | None) -> str | None:
    """Validate an optional HTTP(S) proxy URL without blocking private hosts."""
    value = str(proxy_url or "").strip()
    if not value:
        return None
    normalized, parsed = _validated_http_url(value, label="SearXNG proxy")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("SearXNG proxy must not include a path, query, or fragment")
    return normalized


async def read_limited_searxng_json(
    response: Any,
    *,
    max_bytes: int = SEARXNG_MAX_RESPONSE_BYTES,
) -> Any:
    """Read decoded JSON from a streamed response with a strict byte limit."""
    headers = getattr(response, "headers", {})
    content_encoding = str(headers.get("content-encoding", "") or "").strip().lower()
    if content_encoding not in {"", "identity"}:
        raise ValueError("SearXNG compressed responses are not accepted")
    content_length = str(headers.get("content-length", "") or "").strip()
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = None
        if declared_length is not None and declared_length > max_bytes:
            raise ValueError(f"SearXNG response exceeded {max_bytes} bytes")

    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise ValueError(f"SearXNG response exceeded {max_bytes} bytes")
        chunks.append(chunk)
    return json.loads(b"".join(chunks))


def searxng_endpoint_url(base_url: str, endpoint: str) -> str:
    """Build an endpoint URL; a trailing slash marks an explicit mount path."""
    _normalized, parsed = _validated_http_url(base_url, label="SearXNG URL")

    endpoint_path = "/" + str(endpoint or "").strip().strip("/").lower()
    if endpoint_path not in _SEARXNG_ENDPOINT_PATHS:
        raise ValueError(f"Unsupported SearXNG endpoint: {endpoint}")

    base_path = parsed.path.rstrip("/")
    lowered_path = base_path.lower()
    if not parsed.path.endswith("/"):
        for known_endpoint in _SEARXNG_ENDPOINT_PATHS:
            if lowered_path.endswith(known_endpoint):
                base_path = base_path[: -len(known_endpoint)].rstrip("/")
                break

    path = f"{base_path}{endpoint_path}" if base_path else endpoint_path
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))
