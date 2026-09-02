"""Repository-owned stateless Streamable HTTP MCP integration fixture."""

from __future__ import annotations

import asyncio
import sys

from mcp.server.mcpserver import MCPServer


server = MCPServer(
    name="opensprite-http-test-server",
    version="1.0.0",
    instructions="Deterministic test fixture; never access external systems.",
)


@server.tool(description="Echo one bounded HTTP test value.")
def echo_http(value: str) -> str:
    return value


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        raise SystemExit(2)
    asyncio.run(server.run_streamable_http_async(
        host="127.0.0.1",
        port=int(sys.argv[1]),
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    ))
