"""Adapter from a discovered MCP Tool to the OpenSprite Tool contract."""

from __future__ import annotations

import asyncio

from ..tools.definition import ToolContext, ToolDefinition, ToolResult
from .session import DiscoveredMcpTool, McpClientSession, McpSessionError


class McpToolAdapter:
    def __init__(
        self,
        tool: DiscoveredMcpTool,
        session: McpClientSession,
        invocation_lock: asyncio.Lock,
    ) -> None:
        if tool.definition is None:
            raise ValueError("unsupported MCP tool cannot be adapted")
        self.definition: ToolDefinition = tool.definition
        self._tool = tool
        self._session = session
        self._invocation_lock = invocation_lock

    async def invoke(
        self,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolResult:
        if context.cancellation_event.is_set():
            raise asyncio.CancelledError
        try:
            async with self._invocation_lock:
                content = await self._session.call_tool(
                    self._tool.original_name,
                    arguments,
                )
        except McpSessionError as error:
            raise RuntimeError(error.code) from error
        if context.cancellation_event.is_set():
            raise asyncio.CancelledError
        return ToolResult(
            content=content,
            summary=f"MCP tool completed: {self._tool.original_name}",
        )
