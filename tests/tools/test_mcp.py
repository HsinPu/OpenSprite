import asyncio
from contextlib import AsyncExitStack
import sys
from types import ModuleType, SimpleNamespace

from opensprite.config.schema import MCPServerConfig
from opensprite.tools.mcp import MCPToolWrapper, _http_url_transport_attempts, connect_mcp_servers
from opensprite.tools.registry import ToolRegistry
from opensprite.tools.result_status import classify_tool_result_status


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


def test_implicit_http_transport_tries_streamable_http_before_sse():
    assert _http_url_transport_attempts("https://example.test/mcp") == ["streamableHttp", "sse"]
    assert _http_url_transport_attempts("https://example.test/sse") == ["streamableHttp", "sse"]


def test_connect_mcp_servers_reports_per_server_success_and_failure(monkeypatch):
    closed_sessions = []

    class FakeClientSession:
        def __init__(self, read, write):
            self.server_name = read

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            closed_sessions.append(self.server_name)

        async def initialize(self):
            if self.server_name == "bad":
                raise RuntimeError("unavailable")

        async def list_tools(self):
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name="echo",
                        description="Echo",
                        inputSchema={"type": "object", "properties": {}},
                    )
                ]
            )

    async def fake_open_transport(stack, cfg, transport_type, httpx):
        return cfg.command, object()

    _install_fake_mcp(monkeypatch, FakeClientSession)
    monkeypatch.setattr("opensprite.tools.mcp._open_mcp_transport", fake_open_transport)

    async def scenario():
        registry = ToolRegistry()
        stack = AsyncExitStack()
        await stack.__aenter__()
        summary = await connect_mcp_servers(
            {
                "good": MCPServerConfig(type="stdio", command="good"),
                "bad": MCPServerConfig(type="stdio", command="bad"),
            },
            registry,
            stack,
        )
        assert summary.connected_server_names == ("good",)
        assert summary.failed_server_names == ("bad",)
        assert "RuntimeError: unavailable" in summary.failure_messages["bad"]
        assert registry.get("mcp_good_echo") is not None
        assert registry.get("mcp_bad_echo") is None
        await stack.aclose()

    asyncio.run(scenario())

    assert sorted(closed_sessions) == ["bad", "good"]


def test_connect_mcp_servers_propagates_cancellation_after_cleanup(monkeypatch):
    async def scenario():
        started = asyncio.Event()
        cleanup_calls = []

        class FakeClientSession:
            def __init__(self, read, write):
                self.server_name = read

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                cleanup_calls.append(f"{self.server_name}-session")

            async def initialize(self):
                return None

            async def list_tools(self):
                return SimpleNamespace(
                    tools=[
                        SimpleNamespace(
                            name="echo",
                            description="Echo",
                            inputSchema={"type": "object", "properties": {}},
                        )
                    ]
                )

        async def fake_open_transport(stack, cfg, transport_type, httpx):
            if cfg.command == "good":
                return "good", object()

            async def mark_closed():
                cleanup_calls.append("slow-transport")

            stack.push_async_callback(mark_closed)
            started.set()
            await asyncio.Future()

        _install_fake_mcp(monkeypatch, FakeClientSession)
        monkeypatch.setattr("opensprite.tools.mcp._open_mcp_transport", fake_open_transport)

        registry = ToolRegistry()
        stack = AsyncExitStack()
        await stack.__aenter__()
        task = asyncio.create_task(
            connect_mcp_servers(
                {
                    "good": MCPServerConfig(type="stdio", command="good"),
                    "slow": MCPServerConfig(type="stdio", command="slow"),
                },
                registry,
                stack,
            )
        )
        await started.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("MCP transport cancellation must propagate")
        await stack.aclose()
        return task, cleanup_calls, registry

    task, cleanup_calls, registry = asyncio.run(scenario())

    assert task.cancelled() is True
    assert cleanup_calls == ["slow-transport", "good-session"]
    assert registry.get("mcp_good_echo") is None
