"""MCP connection lifecycle and runtime tool synchronization."""

from __future__ import annotations

import asyncio
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Awaitable, Callable

import opensprite.integrations.mcp.transport as mcp_transport

from ...config.schema import Config, ToolsConfig
from ...core.contracts.run_events import MCP_CONNECTED_EVENT, MCP_CONNECTION_FAILED_EVENT
from ...modules.tools.registry import ToolRegistry
from ...core.contracts.tool_results import tool_error_result
from opensprite.core.logging import logger
from .naming import is_mcp_tool_name


def _mcp_lifecycle_error_result(message: str, *, category: str) -> str:
    return tool_error_result(
        str(message or "").strip(),
        error_type="ConfigureMCPToolError",
        category=category,
        metadata={"tool_name": "configure_mcp"},
    )


class McpLifecycleService:
    """Owns MCP connection state, reconnect backoff, and runtime tool summaries."""

    INITIAL_RETRY_BACKOFF_SECONDS = 15.0
    MAX_RETRY_BACKOFF_SECONDS = 300.0

    def __init__(
        self,
        *,
        tools: ToolRegistry,
        tools_config: ToolsConfig,
        context_builder: Any,
        config_path_getter: Callable[[], Path | None],
        current_session_id_getter: Callable[[], str | None],
        current_run_id_getter: Callable[[], str | None],
        current_channel_getter: Callable[[], str | None],
        current_external_chat_id_getter: Callable[[], str | None],
        emit_run_event: Callable[..., Awaitable[None]],
    ):
        self.tools = tools
        self.tools_config = tools_config
        self.context_builder = context_builder
        self._config_path_getter = config_path_getter
        self._current_session_id_getter = current_session_id_getter
        self._current_run_id_getter = current_run_id_getter
        self._current_channel_getter = current_channel_getter
        self._current_external_chat_id_getter = current_external_chat_id_getter
        self._emit_run_event = emit_run_event
        self.servers = dict(tools_config.mcp_servers)
        self.tool_names: set[str] = set()
        self.connected_server_names: set[str] = set()
        self.failed_server_names: set[str] = set()
        self.stack: AsyncExitStack | None = None
        self.connected = False
        self.connecting = False
        self.connect_failures = 0
        self.retry_after = 0.0
        self._connect_lock = asyncio.Lock()

    async def _emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        session_id = self._current_session_id_getter()
        run_id = self._current_run_id_getter()
        if session_id is None or run_id is None:
            return
        await self._emit_run_event(
            session_id,
            run_id,
            event_type,
            payload,
            channel=self._current_channel_getter(),
            external_chat_id=self._current_external_chat_id_getter(),
        )

    def sync_runtime_tools_context(self) -> None:
        """Expose connected MCP tools to context builders that support prompt summaries."""
        if not hasattr(self.context_builder, "set_runtime_mcp_tools"):
            return

        mcp_tools = sorted(
            [
                (tool.name, tool.description)
                for tool_name in self.tools.tool_names
                for tool in [self.tools.get(tool_name)]
                if tool is not None and is_mcp_tool_name(tool.name)
            ],
            key=lambda item: item[0],
        )
        self.context_builder.set_runtime_mcp_tools(mcp_tools)

    async def _record_connection_failure(
        self,
        *,
        attempted_server_names: set[str],
        failure_messages: dict[str, str],
    ) -> None:
        self.connect_failures += 1
        retry_delay = min(
            self.INITIAL_RETRY_BACKOFF_SECONDS * (2 ** (self.connect_failures - 1)),
            self.MAX_RETRY_BACKOFF_SECONDS,
        )
        self.retry_after = time.monotonic() + retry_delay
        error = "; ".join(
            f"{name}: {failure_messages.get(name, 'unknown connection failure')}"
            for name in sorted(attempted_server_names)
        )
        logger.error(
            "agent.mcp.connect.error | error={} retry_in_s={} failures={}",
            error,
            retry_delay,
            self.connect_failures,
        )
        await self._emit_event(
            MCP_CONNECTION_FAILED_EVENT,
            {
                "server_count": len(self.servers),
                "attempted_server_count": len(attempted_server_names),
                "connected_server_count": len(self.connected_server_names),
                "failed_server_names": sorted(attempted_server_names),
                "error": error,
                "connect_failures": self.connect_failures,
                "retry_in_seconds": retry_delay,
            },
        )

    async def connect(self) -> None:
        """Connect pending MCP servers, sharing one in-flight attempt between callers."""
        if not self.servers:
            return

        async with self._connect_lock:
            configured_server_names = set(self.servers)
            self.connected_server_names.intersection_update(configured_server_names)
            pending_server_names = configured_server_names - self.connected_server_names
            now = time.monotonic()
            if not pending_server_names:
                self.connected = bool(configured_server_names)
                self.failed_server_names.clear()
                return
            if now < self.retry_after:
                return

            self.connecting = True
            attempt_stack: AsyncExitStack | None = None
            preexisting_registry_tool_names = set(self.tools.tool_names)
            previous_tool_names = set(self.tool_names)
            previous_connected_server_names = set(self.connected_server_names)
            previous_failed_server_names = set(self.failed_server_names)
            previous_connect_failures = self.connect_failures
            previous_retry_after = self.retry_after
            try:
                attempt_stack = AsyncExitStack()
                await attempt_stack.__aenter__()
                summary = await mcp_transport.connect_mcp_servers(
                    {name: self.servers[name] for name in sorted(pending_server_names)},
                    self.tools,
                    attempt_stack,
                )
                connected_this_attempt = set(summary.connected_server_names) & pending_server_names
                reported_failures = set(summary.failed_server_names) & pending_server_names
                failed_this_attempt = pending_server_names - connected_this_attempt
                failure_messages = dict(summary.failure_messages)
                for name in failed_this_attempt - reported_failures:
                    failure_messages[name] = "no connection result returned"

                new_tool_names = {
                    name for name in self.tools.tool_names
                    if is_mcp_tool_name(name) and name not in preexisting_registry_tool_names
                }

                if not connected_this_attempt:
                    for name in new_tool_names:
                        self.tools.unregister(name)
                    await attempt_stack.aclose()
                    attempt_stack = None
                    self.failed_server_names = configured_server_names - self.connected_server_names
                    await self._record_connection_failure(
                        attempted_server_names=failed_this_attempt,
                        failure_messages=failure_messages,
                    )
                    return

                self.connected_server_names.update(connected_this_attempt)
                self.failed_server_names = configured_server_names - self.connected_server_names
                self.connected = True
                self.tool_names.update(new_tool_names)
                self.sync_runtime_tools_context()
                await self._emit_event(
                    MCP_CONNECTED_EVENT,
                    {
                        "server_count": len(self.servers),
                        "connected_server_count": len(self.connected_server_names),
                        "connected_server_names": sorted(self.connected_server_names),
                        "failed_server_names": sorted(self.failed_server_names),
                        "tool_names": sorted(self.tool_names),
                        "registered_tool_count": len(self.tool_names),
                    },
                )
                if failed_this_attempt:
                    await self._record_connection_failure(
                        attempted_server_names=failed_this_attempt,
                        failure_messages=failure_messages,
                    )
                else:
                    self.connect_failures = 0
                    self.retry_after = 0.0

                if self.stack is None:
                    self.stack = attempt_stack
                else:
                    self.stack.push_async_callback(attempt_stack.aclose)
                attempt_stack = None
                logger.info("agent.{} | tools={}", MCP_CONNECTED_EVENT, ", ".join(self.tools.tool_names))
            except asyncio.CancelledError:
                for name in list(self.tools.tool_names):
                    if is_mcp_tool_name(name) and name not in preexisting_registry_tool_names:
                        self.tools.unregister(name)
                self.tool_names = previous_tool_names
                self.connected_server_names = previous_connected_server_names
                self.failed_server_names = previous_failed_server_names
                self.connected = bool(previous_connected_server_names)
                self.connect_failures = previous_connect_failures
                self.retry_after = previous_retry_after
                self.sync_runtime_tools_context()
                if attempt_stack is not None:
                    try:
                        await attempt_stack.aclose()
                    except asyncio.CancelledError:
                        raise
                    except Exception as cleanup_exc:
                        logger.warning("agent.mcp.cancel.cleanup.error | error={}", cleanup_exc)
                raise
            except Exception as exc:
                for name in list(self.tools.tool_names):
                    if is_mcp_tool_name(name) and name not in preexisting_registry_tool_names:
                        self.tools.unregister(name)
                if attempt_stack is not None:
                    try:
                        await attempt_stack.aclose()
                    except asyncio.CancelledError:
                        raise
                    except Exception as cleanup_exc:
                        logger.warning("agent.mcp.connect.cleanup.error | error={}", cleanup_exc)
                self.tool_names = previous_tool_names
                self.connected_server_names = previous_connected_server_names
                self.failed_server_names = configured_server_names - previous_connected_server_names
                self.connected = bool(previous_connected_server_names)
                self.connect_failures = previous_connect_failures
                self.retry_after = previous_retry_after
                self.sync_runtime_tools_context()
                await self._record_connection_failure(
                    attempted_server_names=pending_server_names,
                    failure_messages={name: f"{type(exc).__name__}: {exc}" for name in pending_server_names},
                )
            finally:
                self.connecting = False

    async def close(self) -> None:
        """Close any active MCP sessions and reset lifecycle flags."""
        async with self._connect_lock:
            stack = self.stack
            self.stack = None
            self.connected = False
            self.connecting = False
            self.connected_server_names.clear()
            self.failed_server_names.clear()
            self.connect_failures = 0
            self.retry_after = 0.0
            for tool_name in list(self.tool_names):
                self.tools.unregister(tool_name)
            self.tool_names.clear()
            self.sync_runtime_tools_context()

        if stack is None:
            return

        try:
            await stack.aclose()
        except Exception as exc:
            logger.warning("agent.mcp.close.error | error={}", exc)

    async def reload_from_config(self) -> str:
        """Reload MCP settings from disk and reconnect MCP tools."""
        config_path = self._config_path_getter()
        if config_path is None:
            return _mcp_lifecycle_error_result(
                "MCP config path is unavailable.",
                category="missing_config_path",
            )

        loaded = Config.load(config_path)
        self.tools_config.mcp_servers_file = loaded.tools.mcp_servers_file
        self.tools_config.mcp_servers = dict(loaded.tools.mcp_servers)
        self.servers = dict(loaded.tools.mcp_servers)
        self.connect_failures = 0
        self.retry_after = 0.0

        await self.close()
        if not self.servers:
            return "MCP configuration reloaded. No MCP servers are configured now."

        await self.connect()
        if not self.connected:
            return "MCP configuration reloaded, but no MCP servers connected successfully."

        if self.failed_server_names:
            failed_servers = ", ".join(sorted(self.failed_server_names))
            return f"MCP configuration reloaded partially. Retry scheduled for: {failed_servers}"

        connected_tools = ", ".join(sorted(self.tool_names)) or "(none)"
        return f"MCP configuration reloaded. Connected tools: {connected_tools}"
