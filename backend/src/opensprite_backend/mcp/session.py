"""Bounded lifecycle and discovery for one local stdio MCP server."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Final, Protocol, cast

from mcp import Client, StdioServerParameters

from ..tools.definition import ToolDefinition, ToolEffect, ToolSource
from .config import McpServerConfig


_CONNECT_TIMEOUT_SECONDS: Final = 15
_REQUEST_TIMEOUT_SECONDS: Final = 30
_MAX_TOOL_PAGES: Final = 16
_MAX_TOOLS: Final = 128
_MAX_RESULT_CHARS: Final = 65_536


class McpSessionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class McpToolAnnotations:
    read_only: bool
    destructive: bool
    idempotent: bool
    open_world: bool


@dataclass(frozen=True, slots=True)
class DiscoveredMcpTool:
    id: str
    server_id: str
    original_name: str
    title: str | None
    description: str
    annotations: McpToolAnnotations
    definition: ToolDefinition | None
    unsupported_reason: str | None


class McpClientSession(Protocol):
    protocol_version: str
    server_name: str

    async def discover_tools(self) -> tuple[DiscoveredMcpTool, ...]: ...

    async def call_tool(self, original_name: str, arguments: dict[str, object]) -> str: ...

    async def close(self) -> None: ...


class McpSessionFactory(Protocol):
    async def open(self, config: McpServerConfig) -> McpClientSession: ...


class OfficialMcpSessionFactory:
    async def open(self, config: McpServerConfig) -> McpClientSession:
        return await OfficialMcpSession.open(config)


@dataclass(slots=True)
class _SessionCommand:
    kind: str
    future: asyncio.Future[object]
    original_name: str | None = None
    arguments: dict[str, object] | None = None


class OfficialMcpSession:
    def __init__(
        self,
        config: McpServerConfig,
        queue: asyncio.Queue[_SessionCommand],
        owner: asyncio.Task[None],
        protocol_version: str,
        server_name: str,
    ) -> None:
        self._config = config
        self._queue = queue
        self._owner = owner
        self._close_lock = asyncio.Lock()
        self._closed = False
        self.protocol_version = protocol_version
        self.server_name = server_name

    @classmethod
    async def open(cls, config: McpServerConfig) -> "OfficialMcpSession":
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[_SessionCommand] = asyncio.Queue()
        ready: asyncio.Future[tuple[str, str]] = loop.create_future()
        owner = asyncio.create_task(cls._run_owner(config, queue, ready))
        try:
            async with asyncio.timeout(_CONNECT_TIMEOUT_SECONDS):
                protocol_version, server_name = await asyncio.shield(ready)
            return cls(config, queue, owner, protocol_version, server_name)
        except TimeoutError as error:
            owner.cancel()
            await owner
            raise McpSessionError("server_timeout") from error
        except BaseException as error:
            if not owner.done():
                owner.cancel()
                await owner
            if isinstance(error, asyncio.CancelledError):
                raise
            if isinstance(error, McpSessionError):
                raise
            raise McpSessionError("server_start_failed") from error

    async def discover_tools(self) -> tuple[DiscoveredMcpTool, ...]:
        result = await self._request(_SessionCommand(
            kind="discover",
            future=asyncio.get_running_loop().create_future(),
        ))
        return cast(tuple[DiscoveredMcpTool, ...], result)

    async def call_tool(
        self,
        original_name: str,
        arguments: dict[str, object],
    ) -> str:
        result = await self._request(_SessionCommand(
            kind="call",
            future=asyncio.get_running_loop().create_future(),
            original_name=original_name,
            arguments=dict(arguments),
        ))
        return cast(str, result)

    async def close(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
            future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
            self._queue.put_nowait(_SessionCommand(kind="close", future=future))
            try:
                async with asyncio.timeout(10):
                    await asyncio.shield(future)
            except TimeoutError as error:
                self._owner.cancel()
                await self._owner
                raise McpSessionError("server_stop_failed") from error
            await self._owner

    async def _request(self, command: _SessionCommand) -> object:
        if self._closed or self._owner.done():
            raise McpSessionError("server_unreachable")
        self._queue.put_nowait(command)
        return await command.future

    @classmethod
    async def _run_owner(
        cls,
        config: McpServerConfig,
        queue: asyncio.Queue[_SessionCommand],
        ready: asyncio.Future[tuple[str, str]],
    ) -> None:
        stack = AsyncExitStack()
        close_future: asyncio.Future[object] | None = None
        failure: McpSessionError | None = None
        try:
            parameters = StdioServerParameters(
                command=config.executable,
                args=list(config.arguments),
                cwd=config.working_directory,
                env={},
            )
            client = Client(parameters, read_timeout_seconds=_REQUEST_TIMEOUT_SECONDS)
            async with asyncio.timeout(_CONNECT_TIMEOUT_SECONDS):
                await stack.enter_async_context(client)
            if client.server_capabilities is None or client.server_capabilities.tools is None:
                raise McpSessionError("tools_not_supported")
            ready.set_result((
                str(client.protocol_version),
                client.server_info.name if client.server_info is not None else config.name,
            ))
            while True:
                command = await queue.get()
                if command.kind == "close":
                    close_future = command.future
                    break
                try:
                    if command.kind == "discover":
                        result: object = await cls._discover(client, config)
                    elif command.kind == "call" and command.original_name is not None and command.arguments is not None:
                        result = await cls._call(client, command.original_name, command.arguments)
                    else:
                        raise McpSessionError("server_unreachable")
                    if not command.future.done():
                        command.future.set_result(result)
                except McpSessionError as error:
                    if not command.future.done():
                        command.future.set_exception(error)
        except asyncio.CancelledError:
            failure = McpSessionError("server_stop_failed")
        except McpSessionError as error:
            failure = error
        except BaseException:
            failure = McpSessionError("server_start_failed" if not ready.done() else "server_unreachable")
        finally:
            try:
                await stack.aclose()
            except BaseException:
                failure = failure or McpSessionError("server_stop_failed")
            if not ready.done():
                ready.set_exception(failure or McpSessionError("server_start_failed"))
            if close_future is not None and not close_future.done():
                if failure is None:
                    close_future.set_result(None)
                else:
                    close_future.set_exception(failure)
            cls._fail_queued(queue, failure or McpSessionError("server_unreachable"))

    @staticmethod
    def _fail_queued(
        queue: asyncio.Queue[_SessionCommand],
        error: McpSessionError,
    ) -> None:
        while True:
            try:
                command = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if not command.future.done():
                command.future.set_exception(error)

    @staticmethod
    async def _discover(client: Client, config: McpServerConfig) -> tuple[DiscoveredMcpTool, ...]:
        tools: list[DiscoveredMcpTool] = []
        seen_names: set[str] = set()
        cursor: str | None = None
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT_SECONDS):
                for _page in range(_MAX_TOOL_PAGES):
                    result = await client.list_tools(cursor=cursor)
                    for tool in result.tools:
                        if tool.name in seen_names or len(tools) >= _MAX_TOOLS:
                            raise McpSessionError("tool_catalog_invalid")
                        seen_names.add(tool.name)
                        tools.append(_discovered_tool(config.id, tool))
                    cursor = result.next_cursor
                    if cursor is None:
                        return tuple(sorted(tools, key=lambda item: item.id))
                raise McpSessionError("tool_catalog_invalid")
        except McpSessionError:
            raise
        except TimeoutError as error:
            raise McpSessionError("server_timeout") from error
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError):
                raise
            raise McpSessionError("server_unreachable") from error

    @staticmethod
    async def _call(
        client: Client,
        original_name: str,
        arguments: dict[str, object],
    ) -> str:
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT_SECONDS):
                result = await client.call_tool(original_name, arguments)
        except TimeoutError as error:
            raise McpSessionError("server_timeout") from error
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError):
                raise
            raise McpSessionError("server_unreachable") from error
        text_parts = [
            item.text
            for item in result.content
            if getattr(item, "type", None) == "text" and isinstance(getattr(item, "text", None), str)
        ]
        if result.structured_content is not None and not text_parts:
            try:
                structured = json.dumps(result.structured_content, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
            except (TypeError, ValueError) as error:
                raise McpSessionError("tool_result_invalid") from error
            text_parts.append(structured)
        content = "\n".join(text_parts)
        if result.is_error or not content or len(content) > _MAX_RESULT_CHARS:
            raise McpSessionError("tool_result_invalid")
        return content

def _discovered_tool(server_id: str, tool: object) -> DiscoveredMcpTool:
    original_name = getattr(tool, "name", None)
    if not isinstance(original_name, str) or not original_name or len(original_name) > 128:
        raise McpSessionError("tool_catalog_invalid")
    canonical_id = _canonical_tool_id(server_id, original_name)
    title_value = getattr(tool, "title", None)
    title = title_value if isinstance(title_value, str) and 0 < len(title_value) <= 256 else None
    description_value = getattr(tool, "description", None)
    description = description_value if isinstance(description_value, str) and description_value else original_name
    annotations_value = getattr(tool, "annotations", None)
    annotations = McpToolAnnotations(
        read_only=getattr(annotations_value, "read_only_hint", False) is True,
        destructive=getattr(annotations_value, "destructive_hint", True) is not False,
        idempotent=getattr(annotations_value, "idempotent_hint", False) is True,
        open_world=getattr(annotations_value, "open_world_hint", True) is not False,
    )
    input_schema = getattr(tool, "input_schema", None)
    definition: ToolDefinition | None = None
    unsupported_reason: str | None = None
    try:
        normalized_schema = _normalize_schema(input_schema)
        definition = ToolDefinition(
            name=canonical_id,
            description=description,
            input_schema=normalized_schema,
            effect=ToolEffect.SENSITIVE,
            source=ToolSource.MCP,
            source_id=server_id,
            display_name=title or original_name,
            timeout_seconds=_REQUEST_TIMEOUT_SECONDS,
            max_output_chars=_MAX_RESULT_CHARS,
        )
    except (TypeError, ValueError):
        unsupported_reason = "unsupported_schema"
    return DiscoveredMcpTool(
        id=canonical_id,
        server_id=server_id,
        original_name=original_name,
        title=title,
        description=description[:1024],
        annotations=annotations,
        definition=definition,
        unsupported_reason=unsupported_reason,
    )


def _normalize_schema(schema: object) -> dict[str, object]:
    if not isinstance(schema, dict) or schema.get("type") not in {
        "string",
        "integer",
        "number",
        "boolean",
        "object",
        "array",
    }:
        raise ValueError("unsupported MCP schema")
    schema_type = schema["type"]
    allowed = {"type", "description", "enum"}
    if schema_type == "string":
        allowed.update({"minLength", "maxLength"})
    elif schema_type in {"integer", "number"}:
        allowed.update({"minimum", "maximum"})
    elif schema_type == "array":
        allowed.update({"items", "minItems", "maxItems"})
    elif schema_type == "object":
        allowed.update({"properties", "required", "additionalProperties"})
    ignored_metadata = {"title", "default", "$schema"}
    if set(schema) - allowed - ignored_metadata:
        raise ValueError("unsupported MCP schema keyword")
    normalized = {key: value for key, value in schema.items() if key in allowed}
    if schema_type == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError("invalid MCP object properties")
        normalized["properties"] = {
            name: _normalize_schema(child) for name, child in properties.items()
        }
        required = schema.get("required", [])
        if not isinstance(required, list):
            raise ValueError("invalid MCP required fields")
        normalized["required"] = required
        normalized["additionalProperties"] = False
    elif schema_type == "array":
        normalized["items"] = _normalize_schema(schema.get("items"))
    return normalized


def _canonical_tool_id(server_id: str, original_name: str) -> str:
    server_prefix = re.sub(r"[^a-z0-9]", "", server_id.lower())[:8]
    slug = re.sub(r"[^a-z0-9]+", "_", original_name.lower()).strip("_") or "tool"
    digest = sha256(original_name.encode("utf-8")).hexdigest()[:8]
    prefix = f"mcp_{server_prefix}_"
    suffix = f"_{digest}"
    maximum_slug = 64 - len(prefix) - len(suffix)
    return f"{prefix}{slug[:maximum_slug].rstrip('_') or 'tool'}{suffix}"
