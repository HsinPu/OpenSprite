"""Context-building dependency-inversion port."""

from typing import Protocol


class ContextBuilder(Protocol):
    """Build the system prompt and messages consumed by an agent."""

    def build_system_prompt(self, session_id: str = "default") -> str:
        """Build the system prompt."""
        ...

    def build_messages(
        self,
        history: list[dict],
        current_message: str,
        current_images: list[str] | None = None,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """Build the complete message list for an LLM call."""
        ...

    def add_tool_result(
        self,
        messages: list[dict],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> list[dict]:
        """Add a tool result to the messages."""
        ...

    def add_assistant_message(
        self,
        messages: list[dict],
        content: str | None,
        tool_calls: list[dict] | None = None,
    ) -> list[dict]:
        """Add an assistant message, optionally with tool calls."""
        ...
