"""Proactive retrieval helpers for turn-level prompt augmentation."""

from __future__ import annotations

from datetime import datetime

from ..search.base import SearchHit, SearchStore


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
