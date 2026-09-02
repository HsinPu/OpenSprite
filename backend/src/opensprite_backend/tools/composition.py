"""One explicit production registry for the tools shipped by OpenSprite."""

from .builtins import CalculatorTool
from .approval import ToolApprovalAuthorizer
from .receipts import ToolReceiptWriter
from .policy import ReadOnlyToolPolicy
from .registry import ToolRegistry


def create_production_tool_registry(
    approval: ToolApprovalAuthorizer | None = None,
    receipts: ToolReceiptWriter | None = None,
) -> ToolRegistry:
    return ToolRegistry(
        [CalculatorTool()],
        policy=ReadOnlyToolPolicy(),
        approval=approval,
        receipts=receipts,
    )
