"""One explicit production registry for the tools shipped by OpenSprite."""

from .builtins import CalculatorTool
from .policy import ReadOnlyToolPolicy
from .registry import ToolRegistry


def create_production_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [CalculatorTool()],
        policy=ReadOnlyToolPolicy(),
    )
