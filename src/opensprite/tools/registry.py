"""Tool registry for managing available tools."""

from typing import Any, Awaitable, Callable

from .base import Tool
from .evidence import ToolEvidence, build_tool_evidence
from .result_status import tool_error_result


BeforeToolExecuteHook = Callable[[str, dict[str, Any]], Awaitable[None]]


class ToolRegistry:
    """Registry for managing agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self.tool_selection_metadata: dict[str, Any] | None = None

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def registered_tools(self) -> tuple[Tool, ...]:
        """Return every registered tool."""
        return tuple(self._tools.values())

    def unregister(self, name: str) -> Tool | None:
        """Remove one registered tool by name."""
        return self._tools.pop(name, None)

    def filtered(
        self,
        *,
        include_names: set[str] | frozenset[str] | None = None,
        exclude_names: set[str] | frozenset[str] | None = None,
        exposed_only: bool = False,
    ) -> "ToolRegistry":
        """Return a registry copy filtered by included/excluded tool names."""
        del exposed_only
        filtered_registry = ToolRegistry()
        filtered_registry.tool_selection_metadata = self.tool_selection_metadata
        included = include_names
        excluded = exclude_names or set()
        for name, tool in self._tools.items():
            if included is not None and name not in included:
                continue
            if name in excluded:
                continue
            filtered_registry.register(tool)
        return filtered_registry

    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        params: Any,
        *,
        on_before_execute: BeforeToolExecuteHook | None = None,
    ) -> str:
        """Execute a tool by name with given parameters."""
        tool = self._tools.get(name)
        if not tool:
            return _tool_not_available_result(name, self.tool_names)
        display_params = tool.sanitize_params_for_display(params)
        if on_before_execute is not None:
            await on_before_execute(name, display_params if isinstance(display_params, dict) else {})
        return await tool.execute_validated(params)

    def build_evidence(self, name: str, params: Any, result: str, *, ok: bool) -> ToolEvidence:
        """Build tool-specific completion evidence when the tool supports it."""
        tool = self._tools.get(name)
        safe_params = params if isinstance(params, dict) else {}
        if tool is None:
            return build_tool_evidence(name, safe_params, result, ok=ok)
        return tool.build_evidence(safe_params, result, ok=ok)

    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools)


def _tool_not_available_result(tool_name: str, available_tools: list[str]) -> str:
    return tool_error_result(
        f"Tool '{tool_name}' is not available in this turn.",
        error_type="ToolUnavailableError",
        category="tool_unavailable",
        metadata={"available_tools": list(available_tools)},
    )
