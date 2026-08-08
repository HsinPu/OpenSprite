"""MCP transport connection and session ownership."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from ...config.schema import MCPServerConfig
from .tool_adapter import register_mcp_server_tools
from ...modules.tools.registry import ToolRegistry
from opensprite.core.logging import logger


class _ReparentAsyncExitStack:
    """Close a manually-managed AsyncExitStack when the parent AsyncExitStack unwinds."""

    def __init__(self, inner: AsyncExitStack) -> None:
        self._inner = inner

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        await self._inner.aclose()
        return False


@dataclass(frozen=True, slots=True)
class MCPServerConnectionResult:
    """Outcome of connecting one configured MCP server."""

    server_name: str
    connected: bool
    registered_tool_count: int = 0
    transport_type: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MCPConnectionSummary:
    """Per-server results for one MCP connection attempt."""

    server_results: tuple[MCPServerConnectionResult, ...]

    @property
    def connected_server_names(self) -> tuple[str, ...]:
        return tuple(result.server_name for result in self.server_results if result.connected)

    @property
    def failed_server_names(self) -> tuple[str, ...]:
        return tuple(result.server_name for result in self.server_results if not result.connected)

    @property
    def failure_messages(self) -> dict[str, str]:
        return {
            result.server_name: result.error or "unknown connection failure"
            for result in self.server_results
            if not result.connected
        }


def _http_url_transport_attempts(_url: str) -> list[str]:
    return ["streamableHttp", "sse"]


def _use_implicit_http_transport_fallback(cfg: MCPServerConfig) -> bool:
    """When type is omitted and only a URL is given, try streamable HTTP before SSE."""
    return cfg.type is None and bool(cfg.url) and not (cfg.command or "").strip()


def _mcp_connect_timeout_seconds(cfg: MCPServerConfig) -> int:
    return max(1, int(cfg.tool_timeout or 30))


async def _open_mcp_transport(
    stack: AsyncExitStack,
    cfg: MCPServerConfig,
    transport_type: str,
    httpx: Any,
) -> tuple[Any, Any]:
    from mcp import StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    if transport_type == "stdio":
        params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env or None)
        read, write = await stack.enter_async_context(stdio_client(params))
        return read, write
    if transport_type == "sse":

        def httpx_client_factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None,
        ) -> httpx.AsyncClient:
            merged_headers = {
                "Accept": "application/json, text/event-stream",
                **(cfg.headers or {}),
                **(headers or {}),
            }
            return httpx.AsyncClient(
                headers=merged_headers or None,
                follow_redirects=True,
                timeout=timeout or _mcp_connect_timeout_seconds(cfg),
                auth=auth,
            )

        read, write = await stack.enter_async_context(
            sse_client(cfg.url, httpx_client_factory=httpx_client_factory)
        )
        return read, write
    if transport_type == "streamableHttp":
        http_client = await stack.enter_async_context(
            httpx.AsyncClient(
                headers=cfg.headers or None,
                follow_redirects=True,
                timeout=_mcp_connect_timeout_seconds(cfg),
            )
        )
        read, write, _ = await stack.enter_async_context(
            streamable_http_client(cfg.url, http_client=http_client)
        )
        return read, write
    raise ValueError(f"unsupported transport type {transport_type!r}")


async def _connect_mcp_server_transport(
    *,
    name: str,
    cfg: MCPServerConfig,
    transport_type: str,
    registry: ToolRegistry,
    parent_stack: AsyncExitStack,
    httpx: Any,
    client_session_type: Any,
    timeout_seconds: int,
) -> int:
    """Open one transport transactionally and attach it to the attempt stack."""
    server_stack = AsyncExitStack()
    await server_stack.__aenter__()
    preexisting_tool_names = set(registry.tool_names)
    try:
        read, write = await asyncio.wait_for(
            _open_mcp_transport(server_stack, cfg, transport_type, httpx),
            timeout=timeout_seconds,
        )
        session = await server_stack.enter_async_context(client_session_type(read, write))
        await asyncio.wait_for(session.initialize(), timeout=timeout_seconds)
        tools = await asyncio.wait_for(session.list_tools(), timeout=timeout_seconds)
        registered_count = register_mcp_server_tools(registry, name, cfg, session, tools)
        await parent_stack.enter_async_context(_ReparentAsyncExitStack(server_stack))
        return registered_count
    except asyncio.CancelledError:
        for tool_name in set(registry.tool_names) - preexisting_tool_names:
            registry.unregister(tool_name)
        try:
            await server_stack.aclose()
        except asyncio.CancelledError:
            raise
        except Exception as cleanup_exc:
            logger.warning("MCP server '{}': cancellation cleanup failed: {}", name, cleanup_exc)
        raise
    except Exception:
        for tool_name in set(registry.tool_names) - preexisting_tool_names:
            registry.unregister(tool_name)
        await server_stack.aclose()
        raise


async def _connect_mcp_servers_into_stack(
    mcp_servers: dict[str, MCPServerConfig],
    registry: ToolRegistry,
    stack: AsyncExitStack,
) -> MCPConnectionSummary:
    """Connect configured MCP servers into one caller-owned attempt stack."""
    import httpx
    from mcp import ClientSession

    results: list[MCPServerConnectionResult] = []
    for name, cfg in mcp_servers.items():
        timeout_seconds = _mcp_connect_timeout_seconds(cfg)
        try:
            if not cfg.command and not cfg.url:
                error = "no command or url configured"
                logger.warning("MCP server '{}': {}, skipping", name, error)
                results.append(MCPServerConnectionResult(server_name=name, connected=False, error=error))
                continue

            if _use_implicit_http_transport_fallback(cfg):
                ordered = _http_url_transport_attempts(cfg.url)
                last_exc: Exception | None = None
                for transport_type in ordered:
                    try:
                        registered_count = await _connect_mcp_server_transport(
                            name=name,
                            cfg=cfg,
                            transport_type=transport_type,
                            registry=registry,
                            parent_stack=stack,
                            httpx=httpx,
                            client_session_type=ClientSession,
                            timeout_seconds=timeout_seconds,
                        )
                        if transport_type != ordered[0]:
                            logger.info(
                                "MCP server '{}': implicit transport '{}' failed earlier; using '{}'",
                                name,
                                ordered[0],
                                transport_type,
                            )
                        logger.info("MCP server '{}': connected, {} tools registered", name, registered_count)
                        results.append(
                            MCPServerConnectionResult(
                                server_name=name,
                                connected=True,
                                registered_tool_count=registered_count,
                                transport_type=transport_type,
                            )
                        )
                        break
                    except Exception as exc:
                        last_exc = exc
                        logger.warning(
                            "MCP server '{}': transport '{}' connect failed ({}: {})",
                            name,
                            transport_type,
                            type(exc).__name__,
                            exc,
                        )
                else:
                    error = (
                        f"{type(last_exc).__name__}: {last_exc}"
                        if last_exc is not None
                        else "all implicit transports failed"
                    )
                    logger.error(
                        "MCP server '{}': failed after trying transports {}: {}",
                        name,
                        ", ".join(ordered),
                        last_exc,
                    )
                    results.append(
                        MCPServerConnectionResult(
                            server_name=name,
                            connected=False,
                            error=error,
                        )
                    )
                continue

            transport_type = cfg.type
            if not transport_type:
                if cfg.command:
                    transport_type = "stdio"
                elif cfg.url:
                    transport_type = "streamableHttp"
                else:
                    results.append(
                        MCPServerConnectionResult(
                            server_name=name,
                            connected=False,
                            error="transport could not be inferred",
                        )
                    )
                    continue

            if transport_type not in {"stdio", "sse", "streamableHttp"}:
                logger.warning("MCP server '{}': unknown transport type '{}'", name, transport_type)
                results.append(
                    MCPServerConnectionResult(
                        server_name=name,
                        connected=False,
                        transport_type=transport_type,
                        error=f"unknown transport type {transport_type!r}",
                    )
                )
                continue

            registered_count = await _connect_mcp_server_transport(
                name=name,
                cfg=cfg,
                transport_type=transport_type,
                registry=registry,
                parent_stack=stack,
                httpx=httpx,
                client_session_type=ClientSession,
                timeout_seconds=timeout_seconds,
            )
            logger.info("MCP server '{}': connected, {} tools registered", name, registered_count)
            results.append(
                MCPServerConnectionResult(
                    server_name=name,
                    connected=True,
                    registered_tool_count=registered_count,
                    transport_type=transport_type,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("MCP server '{}': failed to connect: {}", name, exc)
            results.append(
                MCPServerConnectionResult(
                    server_name=name,
                    connected=False,
                    transport_type=cfg.type,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    return MCPConnectionSummary(server_results=tuple(results))


async def connect_mcp_servers(
    mcp_servers: dict[str, MCPServerConfig],
    registry: ToolRegistry,
    stack: AsyncExitStack,
) -> MCPConnectionSummary:
    """Connect configured MCP servers transactionally and report each outcome."""
    attempt_stack = AsyncExitStack()
    await attempt_stack.__aenter__()
    preexisting_tool_names = set(registry.tool_names)
    try:
        summary = await _connect_mcp_servers_into_stack(mcp_servers, registry, attempt_stack)
        await stack.enter_async_context(_ReparentAsyncExitStack(attempt_stack))
        return summary
    except asyncio.CancelledError:
        for tool_name in set(registry.tool_names) - preexisting_tool_names:
            registry.unregister(tool_name)
        try:
            await attempt_stack.aclose()
        except asyncio.CancelledError:
            raise
        except Exception as cleanup_exc:
            logger.warning("MCP connection cancellation cleanup failed: {}", cleanup_exc)
        raise
    except Exception:
        for tool_name in set(registry.tool_names) - preexisting_tool_names:
            registry.unregister(tool_name)
        await attempt_stack.aclose()
        raise


__all__ = [
    "MCPConnectionSummary",
    "MCPServerConnectionResult",
    "connect_mcp_servers",
]
