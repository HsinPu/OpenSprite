"""Structural contracts shared by Curator callers."""

from typing import Protocol


class CuratorTurnResult(Protocol):
    """Minimum completed-turn data needed by Curator scheduling policy."""

    executed_tool_calls: int
    used_configure_skill: bool
