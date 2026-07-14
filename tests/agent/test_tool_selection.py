from opensprite.tools.selection import ToolSelectionResolver
from opensprite.tools.base import Tool
from opensprite.tools.registry import ToolRegistry


class DummyTool(Tool):
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Dummy {self._name} tool"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def _execute(self, **kwargs) -> str:
        return "ok"


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name in ("read_file", "web_search", "apply_patch", "batch"):
        registry.register(DummyTool(name))
    return registry


def test_tool_selection_resolver_selects_overlay_tools_and_metadata():
    resolution = ToolSelectionResolver().resolve_overlay(
        _registry(),
        include_names={"read_file", "web_search", "apply_patch", "batch"},
        metadata_kind="subagent",
    )

    assert resolution.registry.tool_names == ["read_file", "web_search", "apply_patch", "batch"]
    assert resolution.registry.tool_selection_metadata == resolution.metadata
    assert resolution.metadata["kind"] == "subagent"
    assert resolution.metadata["tool_selection"]["selected_tools"] == ["read_file", "web_search", "apply_patch", "batch"]
    assert resolution.metadata["tool_selection"]["missing_required_tools"] == []
