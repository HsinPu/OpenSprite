"""Controlled stdio proof for the official MCP Python SDK."""

from __future__ import annotations

import asyncio
from functools import wraps
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters
from mcp.types import TextContent


FIXTURE = Path(__file__).parent / "fixtures" / "mcp_stdio_server.py"


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


@async_test
async def test_official_sdk_negotiates_stdio_lists_and_calls_tools() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(FIXTURE)],
        cwd=FIXTURE.parent,
        env={},
    )

    async with asyncio.timeout(15):
        async with Client(parameters, read_timeout_seconds=5) as client:
            assert client.protocol_version == "2026-07-28"
            assert client.server_info is not None
            assert client.server_info.name == "opensprite-test-server"
            assert client.server_capabilities is not None
            assert client.server_capabilities.tools is not None

            listed = await client.list_tools()
            assert [tool.name for tool in listed.tools] == ["echo", "process_id"]
            assert listed.next_cursor is None

            result = await client.call_tool("echo", {"value": "hello"})
            assert result.is_error is False
            assert result.content == [TextContent(type="text", text="hello")]


def test_sdk_core_dependency_does_not_install_cli_extra() -> None:
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    assert '"mcp>=2,<3"' in pyproject
    assert "mcp[cli]" not in pyproject
    assert 'requires-python = ">=3.12,<3.14"' in pyproject
