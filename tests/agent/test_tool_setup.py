"""Tests for Agent tool registry composition."""

from types import SimpleNamespace

from opensprite.app.agent.tool_setup import setup_agent_tools
from opensprite.modules.tools.registry import ToolRegistry


class _StubTool:
    name = "stub_tool"


def test_setup_agent_tools_uses_injected_default_registrar():
    agent = SimpleNamespace()
    calls = []

    def register_defaults(current_agent):
        calls.append(current_agent)
        current_agent.tools.register(_StubTool())

    registry = setup_agent_tools(
        agent,
        None,
        default_tool_registrar=register_defaults,
    )

    assert calls == [agent]
    assert registry is agent.tools
    assert registry.tool_names == ["stub_tool"]


def test_setup_agent_tools_preserves_preconfigured_registry():
    registry = ToolRegistry()
    registry.register(_StubTool())
    agent = SimpleNamespace()

    def register_defaults(_agent):
        raise AssertionError("preconfigured registries must not be replaced")

    resolved = setup_agent_tools(
        agent,
        registry,
        default_tool_registrar=register_defaults,
    )

    assert resolved is registry
    assert registry.tool_names == ["stub_tool"]


def test_setup_agent_tools_preserves_empty_registry_without_app_composition():
    registry = ToolRegistry()
    agent = SimpleNamespace()

    resolved = setup_agent_tools(agent, registry)

    assert resolved is registry
    assert registry.tool_names == []


def test_agent_uses_injected_memory_tool_registrar(tmp_path):
    from agent_test_helpers import make_agent_loop

    calls = []

    def register_memory(registry, memory_store, get_session_id):
        calls.append((registry, memory_store, get_session_id))

    agent = make_agent_loop(
        tmp_path / "workspace",
        memory_tool_registrar=register_memory,
    )

    assert calls == [
        (
            agent.tools,
            agent.memory,
            agent._get_current_session_id,
        )
    ]
