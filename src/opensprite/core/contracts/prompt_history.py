"""Provider-neutral prompt history contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreparedPromptHistory:
    """Conversation history after prompt-specific filtering and normalization."""

    messages: list[dict[str, Any]]
    loaded_messages: int
    filtered_tool_messages: int
