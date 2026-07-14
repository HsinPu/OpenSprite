import asyncio

from agent_test_helpers import DummyTool, make_agent_loop
from opensprite.bus.message import UserMessage
from opensprite.config.schema import ToolsConfig
from opensprite.tools.mcp import MCPConnectionSummary, MCPServerConnectionResult
from opensprite.tools.result_status import classify_tool_result_status


def _make_agent(tmp_path, tools_config: ToolsConfig | None = None):
    return make_agent_loop(tmp_path, tools_config=tools_config)


def _connection_summary(
    *,
    connected: tuple[str, ...] = (),
    failed: tuple[str, ...] = (),
) -> MCPConnectionSummary:
    return MCPConnectionSummary(
        server_results=(
            *(MCPServerConnectionResult(server_name=name, connected=True) for name in connected),
            *(
                MCPServerConnectionResult(server_name=name, connected=False, error="boom")
                for name in failed
            ),
        )
    )


def test_reload_mcp_from_config_reports_missing_config_path(tmp_path):
    agent = _make_agent(tmp_path)
    agent.config_path = None

    result = asyncio.run(agent.reload_mcp_from_config())
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ConfigureMCPToolError"
    assert status.category == "missing_config_path"
    assert "MCP config path is unavailable" in status.error


def test_connect_mcp_registers_tools_once(tmp_path, monkeypatch):
    calls = []

    async def fake_connect(servers, registry, stack):
        calls.append(sorted(servers.keys()))
        registry.register(DummyTool("mcp_demo_echo"))
        return _connection_summary(connected=("demo",))

    monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)

    agent = _make_agent(
        tmp_path,
        ToolsConfig(mcp_servers={"demo": {"command": "npx", "args": ["demo-mcp"]}}),
    )

    asyncio.run(agent.connect_mcp())
    asyncio.run(agent.connect_mcp())

    assert calls == [["demo"]]
    assert agent.mcp_lifecycle.connected is True
    assert "mcp_demo_echo" in agent.tools.tool_names


def test_connect_mcp_uses_retry_backoff_after_failure(tmp_path, monkeypatch):
    calls = []
    clock = {"now": 100.0}

    async def fake_connect(servers, registry, stack):
        calls.append(sorted(servers.keys()))
        raise RuntimeError("boom")

    monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)
    monkeypatch.setattr("opensprite.runs.trace.time.monotonic", lambda: clock["now"])

    agent = _make_agent(
        tmp_path,
        ToolsConfig(mcp_servers={"demo": {"command": "npx", "args": ["demo-mcp"]}}),
    )

    asyncio.run(agent.connect_mcp())

    assert calls == [["demo"]]
    assert agent.mcp_lifecycle.connected is False
    assert agent.mcp_lifecycle.connect_failures == 1
    assert agent.mcp_lifecycle.retry_after > clock["now"]

    asyncio.run(agent.connect_mcp())
    assert calls == [["demo"]]

    clock["now"] = agent.mcp_lifecycle.retry_after
    asyncio.run(agent.connect_mcp())

    assert calls == [["demo"], ["demo"]]
    assert agent.mcp_lifecycle.connect_failures == 2


def test_connect_mcp_treats_zero_success_summary_as_retryable_failure(tmp_path, monkeypatch):
    async def fake_connect(servers, registry, stack):
        return _connection_summary(failed=("demo",))

    monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)

    agent = _make_agent(
        tmp_path,
        ToolsConfig(mcp_servers={"demo": {"command": "npx", "args": ["demo-mcp"]}}),
    )

    asyncio.run(agent.connect_mcp())

    assert agent.mcp_lifecycle.connected is False
    assert agent.mcp_lifecycle.connected_server_names == set()
    assert agent.mcp_lifecycle.failed_server_names == {"demo"}
    assert agent.mcp_lifecycle.connect_failures == 1
    assert agent.mcp_lifecycle.retry_after > 0


def test_connect_mcp_retries_only_failed_servers_after_partial_success(tmp_path, monkeypatch):
    calls = []
    clock = {"now": 100.0}

    async def fake_connect(servers, registry, stack):
        server_names = tuple(sorted(servers))
        calls.append(server_names)
        if server_names == ("bad", "good"):
            registry.register(DummyTool("mcp_good_echo"))
            return _connection_summary(connected=("good",), failed=("bad",))
        registry.register(DummyTool("mcp_bad_echo"))
        return _connection_summary(connected=("bad",))

    monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)
    monkeypatch.setattr("opensprite.runs.trace.time.monotonic", lambda: clock["now"])

    agent = _make_agent(
        tmp_path,
        ToolsConfig(
            mcp_servers={
                "good": {"command": "npx", "args": ["good-mcp"]},
                "bad": {"command": "npx", "args": ["bad-mcp"]},
            }
        ),
    )

    asyncio.run(agent.connect_mcp())

    assert calls == [("bad", "good")]
    assert agent.mcp_lifecycle.connected is True
    assert agent.mcp_lifecycle.connected_server_names == {"good"}
    assert agent.mcp_lifecycle.failed_server_names == {"bad"}
    assert agent.mcp_lifecycle.connect_failures == 1
    assert "mcp_good_echo" in agent.tools.tool_names

    clock["now"] = agent.mcp_lifecycle.retry_after
    asyncio.run(agent.connect_mcp())

    assert calls == [("bad", "good"), ("bad",)]
    assert agent.mcp_lifecycle.connected_server_names == {"good", "bad"}
    assert agent.mcp_lifecycle.failed_server_names == set()
    assert agent.mcp_lifecycle.connect_failures == 0
    assert agent.mcp_lifecycle.retry_after == 0.0
    assert {"mcp_good_echo", "mcp_bad_echo"} <= set(agent.tools.tool_names)


def test_concurrent_first_connect_waits_for_single_attempt(tmp_path, monkeypatch):
    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def fake_connect(servers, registry, stack):
            calls.append(tuple(sorted(servers)))
            started.set()
            await release.wait()
            registry.register(DummyTool("mcp_demo_echo"))
            return _connection_summary(connected=("demo",))

        monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)
        agent = _make_agent(
            tmp_path,
            ToolsConfig(mcp_servers={"demo": {"command": "npx", "args": ["demo-mcp"]}}),
        )

        first = asyncio.create_task(agent.connect_mcp())
        await started.wait()
        second = asyncio.create_task(agent.connect_mcp())
        await asyncio.sleep(0)
        assert second.done() is False

        release.set()
        await asyncio.gather(first, second)
        return agent, calls

    agent, calls = asyncio.run(scenario())

    assert calls == [("demo",)]
    assert agent.mcp_lifecycle.connected is True
    assert "mcp_demo_echo" in agent.tools.tool_names


def test_connect_mcp_cancellation_cleans_partial_tools_and_stack(tmp_path, monkeypatch):
    async def scenario():
        started = asyncio.Event()
        cleanup_calls = []

        async def fake_connect(servers, registry, stack):
            async def mark_closed():
                cleanup_calls.append("closed")

            stack.push_async_callback(mark_closed)
            registry.register(DummyTool("mcp_demo_echo"))
            started.set()
            await asyncio.Future()

        monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)
        agent = _make_agent(
            tmp_path,
            ToolsConfig(mcp_servers={"demo": {"command": "npx", "args": ["demo-mcp"]}}),
        )

        task = asyncio.create_task(agent.connect_mcp())
        await started.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("MCP connect cancellation must propagate")
        return agent, task, cleanup_calls

    agent, task, cleanup_calls = asyncio.run(scenario())

    assert task.cancelled() is True
    assert cleanup_calls == ["closed"]
    assert agent.mcp_lifecycle.connected is False
    assert agent.mcp_lifecycle.stack is None
    assert agent.mcp_lifecycle.connect_failures == 0
    assert "mcp_demo_echo" not in agent.tools.tool_names


def test_process_saves_input_before_connecting_mcp_and_calling_llm(tmp_path):
    async def scenario():
        agent = _make_agent(tmp_path)
        order = []

        async def fake_connect_mcp():
            order.append("connect")
            assert [(role, content) for _, role, content, *_ in agent.storage.saved] == [
                ("user", "hello")
            ]

        async def fake_call_llm(session_id, current_message, channel=None, user_images=None, allow_tools=True, **kwargs):
            from opensprite.agent.execution import ExecutionResult

            order.append("call_llm")
            assert order[0] == "connect"
            return ExecutionResult(content="assistant reply", executed_tool_calls=0, used_configure_skill=False)

        async def fake_consolidate(session_id):
            order.append("memory")

        async def fake_update_profile(session_id):
            order.append("profile")

        async def fake_update_recent_summary(session_id):
            order.append("recent-summary")

        agent.connect_mcp = fake_connect_mcp
        agent.call_llm = fake_call_llm
        agent._maybe_consolidate_memory = fake_consolidate
        agent._maybe_update_recent_summary = fake_update_recent_summary
        agent._maybe_update_user_profile = fake_update_profile

        response = await agent.process(
            UserMessage(
                text="hello",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
            )
        )
        await agent.wait_for_background_maintenance()
        return response, order

    response, order = asyncio.run(scenario())

    assert order[:2] == ["connect", "call_llm"]
    assert set(order[2:]) == {"memory", "recent-summary", "profile"}
    assert response.text == "assistant reply"


def test_close_mcp_resets_state_and_closes_stack(tmp_path, monkeypatch):
    class FakeStack:
        def __init__(self):
            self.closed = False

        async def __aenter__(self):
            return self

        async def aclose(self):
            self.closed = True

    async def fake_connect(servers, registry, stack):
        return _connection_summary(connected=("demo",))

    monkeypatch.setattr("opensprite.runs.trace.AsyncExitStack", FakeStack)
    monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)

    agent = _make_agent(
        tmp_path,
        ToolsConfig(mcp_servers={"demo": {"command": "npx", "args": ["demo-mcp"]}}),
    )

    asyncio.run(agent.connect_mcp())
    stack = agent.mcp_lifecycle.stack

    assert stack is not None
    assert agent.mcp_lifecycle.connected is True

    asyncio.run(agent.close_mcp())

    assert stack.closed is True
    assert agent.mcp_lifecycle.stack is None
    assert agent.mcp_lifecycle.connected is False


def test_reload_mcp_from_config_replaces_registered_mcp_tools(tmp_path, monkeypatch):
    config_path = tmp_path / "opensprite.json"
    mcp_path = tmp_path / "mcp_servers.json"
    config_path.write_text(
        '{"llm":{"api_key":"key","model":"gpt","temperature":0.7,"max_tokens":2048},'
        '"storage":{"type":"memory","path":"memory.db"},'
        '"channels":{"instances":{"telegram":{"type":"telegram","enabled":false},"web":{"type":"web","enabled":true}}},'
        '"tools":{"mcp_servers_file":"mcp_servers.json"}}',
        encoding="utf-8",
    )
    mcp_path.write_text(
        '{"demo":{"command":"npx","args":["-y","demo-mcp"]}}',
        encoding="utf-8",
    )

    async def fake_connect(servers, registry, stack):
        for server_name in sorted(servers):
            registry.register(DummyTool(f"mcp_{server_name}_echo"))
        return _connection_summary(connected=tuple(sorted(servers)))

    monkeypatch.setattr("opensprite.tools.mcp.connect_mcp_servers", fake_connect)

    agent = _make_agent(
        tmp_path,
        ToolsConfig(mcp_servers={"demo": {"command": "npx", "args": ["demo-mcp"]}}),
    )
    agent.config_path = config_path

    asyncio.run(agent.connect_mcp())
    assert "mcp_demo_echo" in agent.tools.tool_names
    agent.mcp_lifecycle.connect_failures = 3
    agent.mcp_lifecycle.retry_after = 999999.0

    mcp_path.write_text(
        '{"other":{"command":"npx","args":["-y","other-mcp"]}}',
        encoding="utf-8",
    )

    result = asyncio.run(agent.reload_mcp_from_config())

    assert "MCP configuration reloaded." in result
    assert "mcp_other_echo" in agent.tools.tool_names
    assert "mcp_demo_echo" not in agent.tools.tool_names
    assert agent.mcp_lifecycle.connect_failures == 0
    assert agent.mcp_lifecycle.retry_after == 0.0
