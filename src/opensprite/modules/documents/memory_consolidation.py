"""Incremental long-term memory consolidation use case."""

from __future__ import annotations

from typing import Any, Protocol

from ...config.schema import DocumentLlmConfig
from ...core.contracts.persistence import StoredMessage
from ...core.ports.storage import StorageProvider
from ...core.ports.llm import LLMProvider
from ..context.token_counting import count_messages_tokens
from opensprite.core.logging import logger
from .memory import consolidate_memory as _consolidate_memory


class _MemoryStore(Protocol):
    def read(self, session_id: str) -> str: ...

    def write(self, session_id: str, content: str) -> None: ...


class MemoryConsolidationService:
    """Coordinate incremental long-term memory consolidation."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        memory_store: _MemoryStore,
        provider: LLMProvider,
        threshold: int,
        token_threshold: int,
        memory_llm: DocumentLlmConfig,
    ):
        self.storage = storage
        self.memory_store = memory_store
        self.provider = provider
        self.threshold = threshold
        self.token_threshold = token_threshold
        self.memory_llm = memory_llm

    @staticmethod
    def _to_message_dicts(messages: list[StoredMessage | dict[str, Any]]) -> list[dict[str, str]]:
        """Normalize stored messages for the memory consolidation prompt."""
        normalized: list[dict[str, str]] = []
        for message in messages:
            if isinstance(message, dict):
                normalized.append({
                    "role": message.get("role", "?"),
                    "content": message.get("content", ""),
                })
                continue

            normalized.append({
                "role": message.role,
                "content": message.content,
            })
        return normalized

    async def maybe_consolidate(self, session_id: str) -> None:
        """Consolidate pending session history into long-term memory when needed."""
        message_count = await self.storage.get_message_count(session_id)
        last_consolidated = await self.storage.get_consolidated_index(session_id)
        if last_consolidated > message_count:
            await self.storage.set_consolidated_index(session_id, message_count)
            return
        pending_messages = self._to_message_dicts(
            await self.storage.get_messages_slice(
                session_id,
                start_index=last_consolidated,
            )
        )
        unconsolidated = len(pending_messages)
        pending_tokens = count_messages_tokens(pending_messages, model=self.provider.get_default_model()) if pending_messages else 0

        should_consolidate_by_count = self.threshold > 0 and unconsolidated >= self.threshold
        should_consolidate_by_tokens = self.token_threshold > 0 and pending_tokens >= self.token_threshold
        if not should_consolidate_by_count and not should_consolidate_by_tokens:
            return

        logger.info(
            f"[{session_id}] memory.consolidate | pending_messages={unconsolidated} pending_tokens={pending_tokens} "
            f"threshold={self.threshold} token_threshold={self.token_threshold}"
        )
        try:
            success = await _consolidate_memory(
                memory_store=self.memory_store,
                session_id=session_id,
                messages=pending_messages,
                provider=self.provider,
                model=self.provider.get_default_model(),
                memory_llm=self.memory_llm,
            )
            if success:
                await self.storage.set_consolidated_index(session_id, message_count)
                logger.info(f"[{session_id}] memory.consolidated | total_messages={message_count}")
        except Exception as exc:
            logger.error(f"[{session_id}] memory.consolidate.error | error={exc}")
