"""Effect policy for explicitly composed Agent tools."""

from __future__ import annotations

from typing import Protocol

from .definition import ToolDefinition, ToolEffect


class ToolPolicy(Protocol):
    def allows(self, definition: ToolDefinition) -> bool: ...


class ReadOnlyToolPolicy:
    """Initial production policy: only side-effect-free tools may run."""

    def allows(self, definition: ToolDefinition) -> bool:
        return definition.effect is ToolEffect.READ_ONLY
