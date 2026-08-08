"""Agent tool registry setup."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from ...modules.tools.registry import ToolRegistry


DefaultToolRegistrar = Callable[[Any], None]


class MemoryToolRegistrar(Protocol):
    """Register the application-owned durable-memory tool."""

    def __call__(
        self,
        registry: ToolRegistry,
        memory_store: Any,
        get_session_id: Callable[[], str | None],
    ) -> None: ...


def setup_agent_tools(
    agent: Any,
    tools: ToolRegistry | None,
    *,
    default_tool_registrar: DefaultToolRegistrar | None = None,
) -> ToolRegistry:
    """Resolve the tool registry and populate defaults when needed."""
    registry = tools if tools is not None else ToolRegistry()
    if registry.tool_names or default_tool_registrar is None:
        return registry

    agent.tools = registry
    default_tool_registrar(agent)
    return agent.tools
