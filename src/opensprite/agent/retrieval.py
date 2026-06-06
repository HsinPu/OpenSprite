"""Proactive retrieval helpers for turn-level prompt augmentation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..search.base import SearchHit, SearchStore


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
