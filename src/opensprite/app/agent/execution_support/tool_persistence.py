"""Storage persistence helpers for tool execution results."""

from __future__ import annotations

from typing import Any, Awaitable, Callable


class ToolResultPersistence:
    """Persist tool execution results to storage."""

    def __init__(
        self,
        *,
        save_message: Callable[[str, str, str, str | None, dict[str, Any] | None], Awaitable[None]],
    ):
        self.save_message = save_message

    async def persist(
        self,
        *,
        session_id: str | None,
        tool_name: str,
        tool_args: dict[str, Any],
        result: str,
    ) -> None:
        """Persist a single tool result when a target session is available."""
        if session_id is None:
            return

        await self.save_message(
            session_id,
            "tool",
            result,
            tool_name,
            {"tool_args": dict(tool_args or {})},
        )
