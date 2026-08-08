"""MCP integration adapter that exposes external MCP tools as OpenSprite tools."""

from __future__ import annotations

import asyncio
from typing import Any

from opensprite.config.schema import MCPServerConfig
from opensprite.core.contracts.mcp_tools import build_mcp_tool_name
from opensprite.core.logging import logger
from opensprite.modules.tools.base import Tool
from opensprite.modules.tools.registry import ToolRegistry
from opensprite.core.contracts.tool_results import tool_error_result


def _extract_nullable_branch(options: Any) -> tuple[dict[str, Any], bool] | None:
    """Return the single non-null branch for nullable unions."""
    if not isinstance(options, list):
        return None

    non_null: list[dict[str, Any]] = []
    saw_null = False
    for option in options:
        if not isinstance(option, dict):
            return None
        if option.get("type") == "null":
            saw_null = True
            continue
        non_null.append(option)

    if saw_null and len(non_null) == 1:
        return non_null[0], True
    return None


def _normalize_schema_for_openai(schema: Any) -> dict[str, Any]:
    """Normalize nullable JSON Schema patterns for tool definitions."""
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    normalized = dict(schema)

    raw_type = normalized.get("type")
    if isinstance(raw_type, list):
        non_null = [item for item in raw_type if item != "null"]
        if "null" in raw_type and len(non_null) == 1:
            normalized["type"] = non_null[0]
            normalized["nullable"] = True

    for key in ("oneOf", "anyOf"):
        nullable_branch = _extract_nullable_branch(normalized.get(key))
        if nullable_branch is not None:
            branch, _ = nullable_branch
            merged = {k: v for k, v in normalized.items() if k != key}
            merged.update(branch)
            normalized = merged
            normalized["nullable"] = True
            break

    if "properties" in normalized and isinstance(normalized["properties"], dict):
        normalized["properties"] = {
            name: _normalize_schema_for_openai(prop) if isinstance(prop, dict) else prop
            for name, prop in normalized["properties"].items()
        }

    if "items" in normalized and isinstance(normalized["items"], dict):
        normalized["items"] = _normalize_schema_for_openai(normalized["items"])

    if normalized.get("type") != "object":
        return normalized

    normalized.setdefault("properties", {})
    normalized.setdefault("required", [])
    return normalized


class MCPToolWrapper(Tool):
    """Wrap one MCP tool as an OpenSprite-native tool."""

    def __init__(self, session: Any, server_name: str, tool_def: Any, tool_timeout: int = 30):
        self._session = session
        self._original_name = tool_def.name
        self._name = build_mcp_tool_name(server_name, tool_def.name)
        self._description = tool_def.description or tool_def.name
        raw_schema = getattr(tool_def, "inputSchema", None) or {"type": "object", "properties": {}}
        self._parameters = _normalize_schema_for_openai(raw_schema)
        self._tool_timeout = tool_timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def _execute(self, **kwargs: Any) -> str:
        from mcp import types

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._original_name, arguments=kwargs),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '{}' timed out after {}s", self._name, self._tool_timeout)
            return tool_error_result(
                f"MCP tool '{self._name}' timed out after {self._tool_timeout}s.",
                error_type="McpToolError",
                category="mcp_tool_timeout",
                metadata={"tool_name": self._name, "mcp_tool": self._original_name},
            )
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                raise
            logger.warning("MCP tool '{}' was cancelled by server/SDK", self._name)
            return tool_error_result(
                f"MCP tool '{self._name}' was cancelled by server/SDK.",
                error_type="McpToolError",
                category="mcp_tool_cancelled",
                metadata={"tool_name": self._name, "mcp_tool": self._original_name},
            )
        except Exception as exc:
            logger.exception(
                "MCP tool '{}' failed: {}: {}",
                self._name,
                type(exc).__name__,
                exc,
            )
            return tool_error_result(
                f"MCP tool '{self._name}' failed: {type(exc).__name__}: {exc}",
                error_type="McpToolError",
                category="mcp_tool_failed",
                metadata={"tool_name": self._name, "mcp_tool": self._original_name},
            )

        parts: list[str] = []
        for block in getattr(result, "content", []):
            if isinstance(block, types.TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) or "(no output)"


def register_mcp_server_tools(
    registry: ToolRegistry,
    name: str,
    cfg: MCPServerConfig,
    session: Any,
    tools: Any,
) -> int:
    enabled_tools = set(cfg.enabled_tools)
    allow_all_tools = "*" in enabled_tools
    registered_count = 0
    matched_enabled_tools: set[str] = set()
    available_raw_names = [tool_def.name for tool_def in tools.tools]
    available_wrapped_names = [
        build_mcp_tool_name(name, tool_def.name) for tool_def in tools.tools
    ]

    for tool_def in tools.tools:
        wrapped_name = build_mcp_tool_name(name, tool_def.name)
        if (
            not allow_all_tools
            and tool_def.name not in enabled_tools
            and wrapped_name not in enabled_tools
        ):
            logger.debug(
                "MCP: skipping tool '{}' from server '{}' (not in enabled_tools)",
                wrapped_name,
                name,
            )
            continue

        wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=cfg.tool_timeout)
        registry.register(wrapper)
        registered_count += 1
        if enabled_tools:
            if tool_def.name in enabled_tools:
                matched_enabled_tools.add(tool_def.name)
            if wrapped_name in enabled_tools:
                matched_enabled_tools.add(wrapped_name)

    if enabled_tools and not allow_all_tools:
        unmatched_enabled_tools = sorted(enabled_tools - matched_enabled_tools)
        if unmatched_enabled_tools:
            logger.warning(
                "MCP server '{}': enabled_tools entries not found: {}. Available raw names: {}. Available wrapped names: {}",
                name,
                ", ".join(unmatched_enabled_tools),
                ", ".join(available_raw_names) or "(none)",
                ", ".join(available_wrapped_names) or "(none)",
            )

    return registered_count


__all__ = [
    "MCPToolWrapper",
    "register_mcp_server_tools",
]
