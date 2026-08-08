"""Channel adapter port."""

from abc import ABC, abstractmethod
from typing import Any

from ..contracts.messages import AssistantMessage, UserMessage


class MessageAdapter(ABC):
    """Convert platform messages to and from the core message contracts."""

    @abstractmethod
    async def to_user_message(self, raw_message: Any) -> UserMessage:
        """Convert one platform message into the canonical user message."""

    @abstractmethod
    async def send(self, message: AssistantMessage) -> None:
        """Send one canonical assistant message through the channel."""
