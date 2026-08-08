import asyncio
import sys
from types import ModuleType, SimpleNamespace

from opensprite.config.schema import MCPServerConfig
from opensprite.integrations.mcp.tool_adapter import MCPToolWrapper, register_mcp_server_tools
from opensprite.modules.tools.registry import ToolRegistry
from opensprite.core.contracts.tool_results import classify_tool_result_status


class _TextContent:
    def __init__(self, text: str):
        self.text = text


def _install_fake_mcp(monkeypatch, client_session_type=None):
    mod = ModuleType("mcp")
    mod.types = SimpleNamespace(TextContent=_TextContent)
    mod.ClientSession = client_session_type or object
    monkeypatch.setitem(sys.modules, "mcp", mod)


def test_mcp_tool_wrapper_normalizes_nullable_schema_and_executes(monkeypatch):
    _install_fake_mcp(monkeypatch)

    async def call_tool(name, arguments):
        assert name == "echo"
        assert arguments == {"note": "hi"}
        return SimpleNamespace(content=[_TextContent("hello from mcp")])

    tool_def = SimpleNamespace(
        name="echo",
        description="Echo content",
        inputSchema={
            "type": "object",
            "properties": {
                "note": {"type": ["string", "null"]},
            },
        },
    )
    wrapper = MCPToolWrapper(SimpleNamespace(call_tool=call_tool), "demo", tool_def)

    result = asyncio.run(wrapper.execute(note="hi"))

    assert wrapper.name == "mcp_demo_echo"
    assert wrapper.parameters["properties"]["note"]["type"] == "string"
    assert wrapper.parameters["properties"]["note"]["nullable"] is True
    assert result == "hello from mcp"


def test_mcp_tool_wrapper_returns_timeout_message(monkeypatch):
    _install_fake_mcp(monkeypatch)

    async def call_tool(name, arguments):
        await asyncio.sleep(0.05)
        return SimpleNamespace(content=[])

    tool_def = SimpleNamespace(
        name="slow",
        description="Slow tool",
        inputSchema={"type": "object", "properties": {}},
    )
    wrapper = MCPToolWrapper(SimpleNamespace(call_tool=call_tool), "demo", tool_def, tool_timeout=0.01)

    result = asyncio.run(wrapper.execute())
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "McpToolError"
    assert status.category == "mcp_tool_timeout"
    assert "mcp_demo_slow" in status.error


def test_register_mcp_server_tools_accepts_raw_and_wrapped_enabled_names():
    registry = ToolRegistry()
    tool_defs = [
        SimpleNamespace(
            name=name,
            description=name,
            inputSchema={"type": "object", "properties": {}},
        )
        for name in ("raw_name", "wrapped_name", "disabled")
    ]
    cfg = MCPServerConfig(
        type="stdio",
        command="demo",
        enabled_tools=["raw_name", "mcp_demo_wrapped_name"],
        tool_timeout=17,
    )

    registered_count = register_mcp_server_tools(
        registry,
        "demo",
        cfg,
        SimpleNamespace(),
        SimpleNamespace(tools=tool_defs),
    )

    assert registered_count == 2
    assert registry.tool_names == ["mcp_demo_raw_name", "mcp_demo_wrapped_name"]
