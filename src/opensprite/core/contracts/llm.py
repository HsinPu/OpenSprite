"""Provider-neutral LLM message and response contracts."""

from dataclasses import dataclass, field
from typing import Any


CHAT_ROLE_SYSTEM = "system"
CHAT_ROLE_USER = "user"
CHAT_ROLE_ASSISTANT = "assistant"
CHAT_ROLE_TOOL = "tool"
CHAT_CONTENT_TYPE_TEXT = "text"
CHAT_CONTENT_TYPE_IMAGE_URL = "image_url"


@dataclass
class ToolCall:
    """Tool call request from an LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Provider-neutral LLM response."""

    content: str
    model: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None
    reasoning_details: list[dict[str, Any]] | None = None


@dataclass
class ChatMessage:
    """One provider-neutral chat message, optionally containing images."""

    role: str
    content: str | list[dict] = ""
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None
    reasoning_details: list[dict[str, Any]] | None = None

    @staticmethod
    def create_user_message(text: str, images: list[str] | None = None) -> "ChatMessage":
        """Create a user message with optional image data URLs."""
        if images:
            content = [{"type": CHAT_CONTENT_TYPE_TEXT, "text": text}]
            for image in images:
                content.append(
                    {
                        "type": CHAT_CONTENT_TYPE_IMAGE_URL,
                        "image_url": {"url": image},
                    }
                )
            return ChatMessage(role=CHAT_ROLE_USER, content=content)
        return ChatMessage(role=CHAT_ROLE_USER, content=text)


@dataclass
class ToolDefinition:
    """Provider-neutral tool definition for an LLM request."""

    name: str
    description: str
    parameters: dict[str, Any]
