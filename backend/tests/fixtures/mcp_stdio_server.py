"""Repository-owned MCP stdio fixture used only by integration tests."""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer


server = MCPServer(
    name="opensprite-test-server",
    version="1.0.0",
    instructions="Deterministic test fixture; never access external systems.",
)


@server.tool(description="Echo one bounded test value.")
def echo(value: str) -> str:
    return value


@server.tool(description="Return the fixture process id.")
def process_id() -> str:
    return str(os.getpid())


if __name__ == "__main__":
    server.run("stdio")
