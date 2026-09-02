"""Strict persisted configuration for local stdio MCP servers."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Protocol
from uuid import UUID

from ..atomic_file import atomic_write


_SCHEMA_VERSION: Final = 1
_MAX_CONFIG_BYTES: Final = 1024 * 1024
_MAX_SERVERS: Final = 32


class McpConfigStoreError(Exception):
    def __init__(self) -> None:
        super().__init__("MCP server configuration is unavailable.")


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    id: str
    name: str
    executable: str
    arguments: tuple[str, ...]
    working_directory: str | None
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
                        "transport": {
                            "type": "stdio",
                            "executable": item.executable,
                            "arguments": list(item.arguments),
                            "workingDirectory": item.working_directory,
                        },
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
        if type(raw) is not dict or set(raw) != {"version", "servers"} or raw["version"] != _SCHEMA_VERSION or type(raw["servers"]) is not list or len(raw["servers"]) > _MAX_SERVERS:
            raise McpConfigStoreError
        servers: list[McpServerConfig] = []
        for item in raw["servers"]:
            if type(item) is not dict or set(item) != {"id", "name", "enabled", "startOnLaunch", "transport"}:
                raise McpConfigStoreError
            transport = item["transport"]
            if type(transport) is not dict or set(transport) != {"type", "executable", "arguments", "workingDirectory"} or transport["type"] != "stdio" or type(transport["arguments"]) is not list:
                raise McpConfigStoreError
            if len(transport["arguments"]) > 64:
                raise McpConfigStoreError
            try:
                identifier = _text(item["id"], 36)
                if str(UUID(identifier)) != identifier or UUID(identifier).version != 4:
                    raise ValueError("invalid MCP server id")
                name = _text(item["name"], 80)
                if not name.strip():
                    raise ValueError("invalid MCP server name")
                servers.append(
                    McpServerConfig(
                        id=identifier,
                        name=name,
                        executable=_text(transport["executable"], 2048),
                        arguments=tuple(_text(argument, 2048) for argument in transport["arguments"]),
                        working_directory=None if transport["workingDirectory"] is None else _text(transport["workingDirectory"], 2048),
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
