"""Channel-neutral message-bus event contracts."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InboundMessage:
    """Message received from a chat channel."""

    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # User identifier
    external_chat_id: str  # Transport chat/channel identifier
    content: str  # Message text
    session_id: str | None = None  # Internal normalized chat/session identifier
    sender_name: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    images: list[str] = field(default_factory=list)  # base64 image data URLs
    audios: list[str] = field(default_factory=list)  # base64 audio data URLs
    videos: list[str] = field(default_factory=list)  # base64 video data URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    raw: Any = None

    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        return self.session_id or f"{self.channel}:{self.external_chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a chat channel."""

    channel: str
    external_chat_id: str  # Transport chat/channel identifier
    content: str
    session_id: str | None = None
    reply_to: str | None = None
    images: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


@dataclass
class RunEvent:
    """Structured status event emitted while a user-facing run executes."""

    channel: str
    external_chat_id: str
    session_id: str
    run_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class SessionStatusEvent:
    """Transient status update for one normalized session."""

    session_id: str
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)
