"""Conversation history load/save and retrieval helpers for AgentLoop."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Awaitable, Callable

from ..llms import ChatMessage
from ..runs.events import SEARCH_INDEX_MESSAGE_FAILED_EVENT
from ..search.base import SearchHit, SearchStore
from ..storage import StorageProvider, StoredMessage
from ..utils.log import logger

HISTORY_SEARCH_TOOL_NAME = "search_history"
HISTORY_RESULT_COUNT_METADATA_KEYS = ("result_count", "hit_count", "hits", "count")
HISTORY_RECALLED_ITEMS_INSUFFICIENT_REASON = "assistant did not provide enough recalled items"


def is_history_retrieval_tool_name(tool_name: str | None) -> bool:
    """Return whether a tool name represents chat-history retrieval."""
    return str(tool_name or "").strip() == HISTORY_SEARCH_TOOL_NAME


def history_retrieval_metadata_reports_empty(metadata: dict[str, Any] | None) -> bool:
    """Return whether search-history metadata explicitly reports zero matches."""
    if not isinstance(metadata, dict):
        return False
    saw_count_field = False
    for key in HISTORY_RESULT_COUNT_METADATA_KEYS:
        if key not in metadata:
            continue
        value = metadata.get(key)
        if _metadata_value_has_results(value):
            return False
        saw_count_field = True
    return saw_count_field


def history_retrieval_metadata_has_results(metadata: dict[str, Any] | None) -> bool:
    """Return whether search-history metadata explicitly reports one or more matches."""
    if not isinstance(metadata, dict):
        return False
    return any(
        _metadata_value_has_results(metadata.get(key))
        for key in HISTORY_RESULT_COUNT_METADATA_KEYS
        if key in metadata
    )


def _metadata_value_has_results(value: object) -> bool:
    if isinstance(value, list):
        return len(value) > 0
    return _coerce_int(value, default=0) > 0


def _coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                return int(float(stripped))
            except ValueError:
                return default
    return default


def _reasoning_details_from_metadata(metadata: dict[str, Any]) -> list[dict[str, Any]] | None:
    details = metadata.get("llm_reasoning_details")
    return details if isinstance(details, list) else None


class MessageHistoryService:
    """Loads session history and persists messages with optional search indexing."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        search_store: SearchStore | None,
        max_history_getter: Callable[[], int],
        emit_index_failure: Callable[[str, str, dict[str, Any]], Awaitable[None]] | None = None,
    ):
        self.storage = storage
        self.search_store = search_store
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
                metadata = message.get("metadata", {}) if isinstance(message.get("metadata", {}), dict) else {}
                chat_messages.append(ChatMessage(
                    role=message.get("role", "?"),
                    content=message.get("content", ""),
                    reasoning_details=_reasoning_details_from_metadata(metadata),
                ))
            else:
                metadata = message.metadata if isinstance(message.metadata, dict) else {}
                chat_messages.append(ChatMessage(
                    role=message.role,
                    content=message.content,
                    reasoning_details=_reasoning_details_from_metadata(metadata),
                ))

        return chat_messages

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
        if self.search_store is None:
            return

        try:
            await self.search_store.index_message(
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


class HistoryResetService:
    """Clears session history and related per-session derived state."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        search_store: SearchStore | None,
        clear_session_artifacts: Callable[[str], Awaitable[None]],
    ):
        self.storage = storage
        self.search_store = search_store
        self._clear_session_artifacts = clear_session_artifacts

    async def reset(self, session_id: str | None = None) -> None:
        """Clear one session or all sessions from storage and derived indexes."""
        if session_id:
            await self._clear_one(session_id)
            return

        all_sessions = await self.storage.get_all_sessions()
        for current_session_id in all_sessions:
            await self._clear_one(current_session_id)

    async def _clear_one(self, session_id: str) -> None:
        await self.storage.clear_messages(session_id)
        await self._clear_session_artifacts(session_id)
        if self.search_store is None:
            return
        try:
            await self.search_store.clear_session(session_id)
        except Exception as e:
            logger.warning("[{}] Failed to clear search index: {}", session_id, e)


class ProactiveRetrievalService:
    """Fetch compact prior context when the task-context resolver asks for it."""

    def __init__(self, *, search_store: SearchStore | None):
        self.search_store = search_store

    async def build_context(
        self,
        *,
        session_id: str,
        current_message: str,
        should_retrieve: bool | None = None,
    ) -> str:
        if self.search_store is None or not bool(should_retrieve):
            return ""

        history_hits = await self.search_store.search_history(session_id=session_id, query=current_message, limit=3)
        if not history_hits:
            return ""

        sections = [
            "# Proactive Retrieval Context",
            "The task-context resolver selected prior chat retrieval. Use the snippets below before asking the user to restate information.",
            "",
            "## Retrieved History",
            *self._format_history_hits(history_hits),
        ]
        return "\n".join(sections).strip()

    @staticmethod
    def _format_time(created_at: float) -> str:
        if not created_at:
            return "unknown"
        return datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _truncate(text: str, limit: int = 180) -> str:
        normalized = " ".join(str(text or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3] + "..."

    def _format_history_hits(self, hits: list[SearchHit]) -> list[str]:
        lines: list[str] = []
        for index, hit in enumerate(hits, start=1):
            label = hit.role or "message"
            if hit.tool_name:
                label = f"{label}:{hit.tool_name}"
            lines.append(f"{index}. [{label}] {self._format_time(hit.created_at)}")
            lines.append(f"   {self._truncate(hit.content)}")
        return lines
