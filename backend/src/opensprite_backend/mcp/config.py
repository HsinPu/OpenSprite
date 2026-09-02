"""Strict persisted configuration for supported MCP transports."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal, Protocol
from uuid import UUID

from ..atomic_file import atomic_write
from .network import McpNetworkPolicyError, normalize_streamable_http_url


_SCHEMA_VERSION: Final = 3
_MAX_CONFIG_BYTES: Final = 1024 * 1024
_MAX_SERVERS: Final = 32


class McpConfigStoreError(Exception):
    def __init__(self) -> None:
        super().__init__("MCP server configuration is unavailable.")


@dataclass(frozen=True, slots=True)
class McpStdioConfig:
    executable: str
    arguments: tuple[str, ...]
    working_directory: str | None

    @property
    def type(self) -> Literal["stdio"]:
        return "stdio"


@dataclass(frozen=True, slots=True)
class McpStreamableHttpConfig:
    url: str

    @property
    def type(self) -> Literal["streamable-http"]:
        return "streamable-http"


McpTransportConfig = McpStdioConfig | McpStreamableHttpConfig


@dataclass(frozen=True, slots=True)
class McpNoAuthenticationConfig:
    @property
    def type(self) -> Literal["none"]:
        return "none"


@dataclass(frozen=True, slots=True)
class McpBearerAuthenticationConfig:
    @property
    def type(self) -> Literal["bearer-token"]:
        return "bearer-token"


McpAuthenticationConfig = McpNoAuthenticationConfig | McpBearerAuthenticationConfig


def mcp_bearer_credential_id(server_id: str) -> str:
    """Return the fixed encrypted-store key for one MCP Bearer token."""

    return f"mcp:{server_id}:bearer"


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    id: str
    name: str
    transport: McpTransportConfig
    authentication: McpAuthenticationConfig = McpNoAuthenticationConfig()
    enabled: bool = False
    start_on_launch: bool = False

    def with_enabled(self, enabled: bool) -> "McpServerConfig":
        return replace(self, enabled=enabled)


class McpConfigStore(Protocol):
    def get(self) -> tuple[McpServerConfig, ...]: ...

    def set(self, servers: tuple[McpServerConfig, ...]) -> None: ...


class JsonMcpConfigStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> tuple[McpServerConfig, ...]:
        raw = self._read()
        if raw is None:
            return ()
        return self._decode(raw)

    def set(self, servers: tuple[McpServerConfig, ...]) -> None:
        if len(servers) > _MAX_SERVERS or len({item.id for item in servers}) != len(servers):
            raise McpConfigStoreError
        payload = json.dumps(
            {
                "version": _SCHEMA_VERSION,
                "servers": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "enabled": item.enabled,
                        "startOnLaunch": item.start_on_launch,
                        "transport": _encode_transport(item.transport),
                        "authentication": _encode_authentication(item.authentication),
                    }
                    for item in sorted(servers, key=lambda server: server.id)
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > _MAX_CONFIG_BYTES:
            raise McpConfigStoreError
        try:
            atomic_write(self._path, payload)
        except Exception as error:
            raise McpConfigStoreError from error

    def _read(self) -> object | None:
        try:
            with self._path.open("rb") as stream:
                data = stream.read(_MAX_CONFIG_BYTES + 1)
        except FileNotFoundError:
            return None
        except Exception as error:
            raise McpConfigStoreError from error
        if len(data) > _MAX_CONFIG_BYTES:
            raise McpConfigStoreError
        try:
            return json.loads(
                data.decode("utf-8"),
                object_pairs_hook=self._without_duplicate_keys,
            )
        except Exception as error:
            raise McpConfigStoreError from error

    @staticmethod
    def _without_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value

    @staticmethod
    def _decode(raw: object) -> tuple[McpServerConfig, ...]:
        if type(raw) is not dict or set(raw) != {"version", "servers"} or raw["version"] not in {1, 2, _SCHEMA_VERSION} or type(raw["servers"]) is not list or len(raw["servers"]) > _MAX_SERVERS:
            raise McpConfigStoreError
        servers: list[McpServerConfig] = []
        for item in raw["servers"]:
            expected_keys = {"id", "name", "enabled", "startOnLaunch", "transport"}
            if raw["version"] == _SCHEMA_VERSION:
                expected_keys.add("authentication")
            if type(item) is not dict or set(item) != expected_keys:
                raise McpConfigStoreError
            transport = item["transport"]
            if type(transport) is not dict:
                raise McpConfigStoreError
            if raw["version"] == 1 and transport.get("type") != "stdio":
                raise McpConfigStoreError
            try:
                identifier = _text(item["id"], 36)
                if str(UUID(identifier)) != identifier or UUID(identifier).version != 4:
                    raise ValueError("invalid MCP server id")
                name = _text(item["name"], 80)
                if not name.strip():
                    raise ValueError("invalid MCP server name")
                decoded_transport = _decode_transport(transport)
                decoded_authentication = (
                    McpNoAuthenticationConfig()
                    if raw["version"] in {1, 2}
                    else _decode_authentication(item["authentication"])
                )
                if (
                    isinstance(decoded_transport, McpStdioConfig)
                    and isinstance(
                        decoded_authentication,
                        McpBearerAuthenticationConfig,
                    )
                ):
                    raise ValueError("stdio cannot use HTTP authentication")
                servers.append(
                    McpServerConfig(
                        id=identifier,
                        name=name,
                        transport=decoded_transport,
                        authentication=decoded_authentication,
                        enabled=_boolean(item["enabled"]),
                        start_on_launch=_boolean(item["startOnLaunch"]),
                    )
                )
            except (TypeError, ValueError) as error:
                raise McpConfigStoreError from error
        if len({item.id for item in servers}) != len(servers):
            raise McpConfigStoreError
        return tuple(sorted(servers, key=lambda server: server.id))


def _text(value: object, maximum: int) -> str:
    if type(value) is not str or not value or len(value) > maximum or any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError("invalid MCP configuration text")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("invalid MCP configuration boolean")
    return value


def _encode_transport(transport: McpTransportConfig) -> dict[str, object]:
    if isinstance(transport, McpStdioConfig):
        return {
            "type": "stdio",
            "executable": transport.executable,
            "arguments": list(transport.arguments),
            "workingDirectory": transport.working_directory,
        }
    return {"type": "streamable-http", "url": transport.url}


def _decode_transport(raw: dict[object, object]) -> McpTransportConfig:
    if raw.get("type") == "stdio":
        if set(raw) != {"type", "executable", "arguments", "workingDirectory"} or type(raw["arguments"]) is not list or len(raw["arguments"]) > 64:
            raise ValueError("invalid stdio transport")
        return McpStdioConfig(
            executable=_text(raw["executable"], 2048),
            arguments=tuple(_text(argument, 2048) for argument in raw["arguments"]),
            working_directory=None if raw["workingDirectory"] is None else _text(raw["workingDirectory"], 2048),
        )
    if raw.get("type") == "streamable-http":
        if set(raw) != {"type", "url"}:
            raise ValueError("invalid Streamable HTTP transport")
        return McpStreamableHttpConfig(url=_validated_http_url(raw["url"]))
    raise ValueError("unknown MCP transport")


def _encode_authentication(
    authentication: McpAuthenticationConfig,
) -> dict[str, object]:
    return {"type": authentication.type}


def _decode_authentication(raw: object) -> McpAuthenticationConfig:
    if type(raw) is not dict or set(raw) != {"type"}:
        raise ValueError("invalid MCP authentication")
    if raw["type"] == "none":
        return McpNoAuthenticationConfig()
    if raw["type"] == "bearer-token":
        return McpBearerAuthenticationConfig()
    raise ValueError("unknown MCP authentication")


def _validated_http_url(value: object) -> str:
    try:
        return normalize_streamable_http_url(_text(value, 2048))
    except McpNetworkPolicyError as error:
        raise ValueError("invalid Streamable HTTP URL") from error
