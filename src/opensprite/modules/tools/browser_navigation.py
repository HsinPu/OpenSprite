"""Pure navigation safety policy shared by browser-facing adapters."""

from __future__ import annotations

import re
from ipaddress import ip_address
from urllib.parse import unquote, urlparse


_SECRET_IN_URL_RE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|(?:api[_-]?key|token|secret|password)=([^&#]{8,}))",
    re.IGNORECASE,
)
_ALWAYS_BLOCKED_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})
_PRIVATE_HOST_SUFFIXES = (".local", ".lan", ".internal")


def validate_navigation_url(url: str, *, allow_private_urls: bool = False) -> str:
    """Return an explanatory block reason, or an empty string when the URL is safe."""
    decoded_url = unquote(str(url or "").strip())
    parsed = urlparse(decoded_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "Blocked: browser_navigate only accepts absolute http or https URLs."
    if _SECRET_IN_URL_RE.search(decoded_url):
        return "Blocked: URL appears to contain a secret or credential."

    host = (parsed.hostname or "").strip().lower().strip(".")
    if host in _ALWAYS_BLOCKED_HOSTS:
        return "Blocked: URL targets a cloud metadata endpoint."
    if not allow_private_urls and _is_private_host(host):
        return "Blocked: URL targets a private or internal host."
    return ""


def _is_private_host(host: str) -> bool:
    if not host:
        return True
    if host in {"localhost", "localhost.localdomain"} or host.endswith(_PRIVATE_HOST_SUFFIXES):
        return True
    try:
        address = ip_address(host.strip("[]"))
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved
