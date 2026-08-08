"""Conversation history loading, prompt preparation, and persistence."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from ...core.contracts.persistence import StoredMessage
from ...core.contracts.prompt_history import PreparedPromptHistory as _PreparedPromptHistory
from ...core.contracts.run_events import SEARCH_INDEX_MESSAGE_FAILED_EVENT
from ...core.contracts.tool_names import HISTORY_SEARCH_TOOL_NAME
from ...core.ports.search import SearchStore
from ...core.ports.storage import StorageProvider
from ...core.contracts.llm import CHAT_ROLE_ASSISTANT, CHAT_ROLE_TOOL, CHAT_ROLE_USER, ChatMessage
from opensprite.core.logging import logger


def _reasoning_details_from_metadata(metadata: dict[str, Any]) -> list[dict[str, Any]] | None:
    details = metadata.get("llm_reasoning_details")
    return details if isinstance(details, list) else None


class MessageHistoryService:
    """Loads session history and persists messages with optional search indexing."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        history_search_store: SearchStore | None,
        max_history_getter: Callable[[], int],
        emit_index_failure: Callable[[str, str, dict[str, Any]], Awaitable[None]] | None = None,
    ):
        self.storage = storage
        self.history_search_store = history_search_store
        self._max_history_getter = max_history_getter
        self._emit_index_failure = emit_index_failure

    async def load_history(self, session_id: str) -> list[ChatMessage]:
        """Load conversation history as ChatMessage objects for LLM consumption."""
        stored_messages = await self.storage.get_messages(
            session_id,
            limit=self._max_history_getter(),
        )

        chat_messages = []
        for message in stored_messages:
            if isinstance(message, dict):
                metadata = (
                    message.get("metadata", {})
                    if isinstance(message.get("metadata", {}), dict)
                    else {}
                )
                chat_messages.append(
                    ChatMessage(
                        role=message.get("role", "?"),
                        content=message.get("content", ""),
                        reasoning_details=_reasoning_details_from_metadata(metadata),
                    )
                )
            else:
                metadata = message.metadata if isinstance(message.metadata, dict) else {}
                chat_messages.append(
                    ChatMessage(
                        role=message.role,
                        content=message.content,
                        reasoning_details=_reasoning_details_from_metadata(metadata),
                    )
                )

        return chat_messages

    async def load_prompt_history(
        self,
        session_id: str,
        current_message: str,
    ) -> _PreparedPromptHistory:
        """Load and normalize conversation history for one LLM prompt."""
        return self.prepare_prompt_history(
            await self.load_history(session_id),
            current_message=current_message,
        )

    @classmethod
    def prepare_prompt_history(
        cls,
        history_messages: list[ChatMessage | dict[str, Any]],
        *,
        current_message: str,
    ) -> _PreparedPromptHistory:
        """Filter turn-local artifacts and return prompt-ready history dicts."""
        loaded_messages = len(history_messages)
        prompt_messages = [
            message
            for message in history_messages
            if cls._message_role(message) != CHAT_ROLE_TOOL
        ]
        filtered_tool_messages = loaded_messages - len(prompt_messages)

        if prompt_messages:
            latest = prompt_messages[-1]
            if (
                cls._message_role(latest) == CHAT_ROLE_USER
                and cls._message_content(latest) == current_message
            ):
                prompt_messages = prompt_messages[:-1]

        return _PreparedPromptHistory(
            messages=[cls._message_to_prompt_dict(message) for message in prompt_messages],
            loaded_messages=loaded_messages,
            filtered_tool_messages=filtered_tool_messages,
        )

    @staticmethod
    def _message_role(message: ChatMessage | dict[str, Any]) -> str:
        return str(
            message.get("role", "?")
            if isinstance(message, dict)
            else getattr(message, "role", "?")
        )

    @staticmethod
    def _message_content(message: ChatMessage | dict[str, Any]) -> Any:
        return (
            message.get("content", "")
            if isinstance(message, dict)
            else getattr(message, "content", "")
        )

    @classmethod
    def _message_to_prompt_dict(
        cls,
        message: ChatMessage | dict[str, Any],
    ) -> dict[str, Any]:
        if isinstance(message, dict):
            prompt_message: dict[str, Any] = {
                "role": message.get("role", "?"),
                "content": message.get("content", ""),
            }
            if message.get("tool_call_id"):
                prompt_message["tool_call_id"] = message["tool_call_id"]
            if message.get("reasoning_details"):
                prompt_message["reasoning_details"] = message["reasoning_details"]
            return prompt_message

        prompt_message = {
            "role": message.role,
            "content": message.content,
        }
        if getattr(message, "tool_call_id", None):
            prompt_message["tool_call_id"] = message.tool_call_id
        if getattr(message, "reasoning_details", None):
            prompt_message["reasoning_details"] = message.reasoning_details
        return prompt_message

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save one message to storage and index it when search is configured."""
        created_at = time.time()
        await self.storage.add_message(
            session_id,
            StoredMessage(
                role=role,
                content=content,
                timestamp=created_at,
                tool_name=tool_name,
                metadata=dict(metadata or {}),
            ),
        )
        if role == CHAT_ROLE_TOOL and tool_name == HISTORY_SEARCH_TOOL_NAME:
            return
        if self.history_search_store is None:
            return

        try:
            await self.history_search_store.index_message(
                session_id=session_id,
                role=role,
                content=content,
                tool_name=tool_name,
                created_at=created_at,
            )
        except Exception as e:
            logger.warning("[{}] Failed to index message for search: {}", session_id, e)
            if self._emit_index_failure is not None:
                await self._emit_index_failure(
                    session_id,
                    SEARCH_INDEX_MESSAGE_FAILED_EVENT,
                    {
                        "role": role,
                        "tool_name": tool_name,
                        "content_len": len(str(content or "")),
                        "error": str(e),
                    },
                )

    async def save_user_message(
        self,
        session_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist and index a visible user message."""
        await self.save_message(
            session_id,
            CHAT_ROLE_USER,
            content,
            metadata=metadata,
        )

    async def save_assistant_message(
        self,
        session_id: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist and index a visible assistant message."""
        await self.save_message(
            session_id,
            CHAT_ROLE_ASSISTANT,
            content,
            metadata=metadata,
        )
