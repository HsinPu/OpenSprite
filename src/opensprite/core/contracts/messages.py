"""Channel-neutral user and assistant message contracts."""

from dataclasses import dataclass, field
from typing import Any


CLIENT_TURN_ID_METADATA_KEY = "client_turn_id"
RESPONSE_KIND_METADATA_KEY = "response_kind"
SESSION_COMMAND_RESPONSE_KIND = "session_command"
TURN_SOURCE_METADATA_KEY = "source"
CLI_VIA_WEB_TURN_SOURCE = "cli_via_web"


@dataclass
class UserMessage:
    """A channel-neutral user message passed into the agent runtime."""

    text: str
    channel: str = "unknown"
    external_chat_id: str | None = None
    session_id: str | None = None
    sender_id: str | None = None
    sender_name: str | None = None
    images: list[str] | None = None
    audios: list[str] | None = None
    videos: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


@dataclass
class AssistantMessage:
    """A channel-neutral assistant response returned by the agent runtime."""

    text: str
    channel: str = "unknown"
    external_chat_id: str | None = None
    session_id: str | None = None
    images: list[str] | None = None
    voices: list[str] | None = None
    audios: list[str] | None = None
    videos: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any = None
