"""Provider identity and protocol contracts, independent of HTTP adapters."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from typing import Literal, TYPE_CHECKING
from unicodedata import normalize
from urllib.parse import urlsplit, urlunsplit
from opensprite_backend.provider_identity import require_provider_id

if TYPE_CHECKING:
    from opensprite_backend.inference.capabilities import ModelCapability

BUILTIN_PROVIDER_IDS = frozenset({"openai", "anthropic", "openrouter"})
ProviderProtocol = Literal["openai_responses", "anthropic_messages", "openrouter", "openai_chat_completions"]


def valid_provider_id(value: object) -> bool:
    """Accept unchanged built-in IDs or canonical UUIDs, never arbitrary keys."""
    if not isinstance(value, str):
        return False
    if value in BUILTIN_PROVIDER_IDS:
        return True
    try:
        require_provider_id(value)
    except ValueError:
        return False
    return True


def provider_name(value: str) -> str:
    result = normalize("NFC", value).strip()
    if not 1 <= len(result) <= 80 or any(ord(char) < 32 for char in result):
        raise ValueError("invalid_provider_name")
    return result


def canonical_base_url(value: str, *, allow_insecure_local: bool = False) -> str:
    """Validate configured endpoints without resolving DNS or making requests.

    HTTP is restricted to explicit loopback/private addresses or localhost.
    DNS names require HTTPS; redirects remain disabled by the HTTP boundary.
    """
    if not value or value != value.strip() or any(ord(char) < 33 for char in value):
        raise ValueError("invalid_base_url")
    if "\\" in value or "?" in value or "#" in value:
        raise ValueError("invalid_base_url")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise ValueError("invalid_base_url") from None
    if parts.scheme not in {"http", "https"} or not host or parts.username is not None or parts.password is not None:
        raise ValueError("invalid_base_url")
    if "%" in host or any(segment in {".", ".."} for segment in parts.path.split("/")):
        raise ValueError("invalid_base_url")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None and (address.is_unspecified or address.is_multicast or address.is_link_local):
        raise ValueError("invalid_base_url")
    local = host.lower() == "localhost" or (address is not None and (address.is_loopback or address.is_private))
    if parts.scheme == "http" and not (allow_insecure_local and local):
        raise ValueError("insecure_base_url")
    hostname = host.lower().encode("idna").decode("ascii")
    authority = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        if port == 0:
            raise ValueError("invalid_base_url")
        authority += f":{port}"
    return urlunsplit((parts.scheme, authority, parts.path.rstrip("/"), "", ""))


@dataclass(frozen=True, slots=True)
class ProviderEndpointSnapshot:
    """Non-secret execution identity retained for a complete Run."""

    provider_id: str
    revision: int
    protocol: ProviderProtocol
    base_url: str
    auth_mode: Literal["none", "bearer"]
    models: tuple[ModelCapability, ...] = ()
    non_streaming_tools: bool = False
    tools_enabled: bool = True
    disabled_models: tuple[str, ...] = ()

    def endpoint(self, resource: Literal["models", "chat/completions"]) -> str:
        return f"{self.base_url}/{resource}"
