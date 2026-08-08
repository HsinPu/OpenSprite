"""Prompt rendering policy for durable session documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _PromptDocumentReader(Protocol):
    def read(self, session_id: str) -> str: ...


@dataclass(frozen=True)
class PromptMemoryDocument:
    """One durable memory document rendered for prompt injection."""

    title: str
    content: str

    def render(self) -> str:
        """Render this memory document as a system-prompt section."""
        content = str(self.content or "").strip()
        if not content:
            return ""
        return f"# {self.title}\n\n{PromptMemoryDocumentService.size_hint(content)}\n\n{content}"


class PromptMemoryDocumentService:
    """Loads durable memory documents and renders prompt-ready sections."""

    def __init__(
        self,
        *,
        memory_store: _PromptDocumentReader,
        recent_summary_store: _PromptDocumentReader,
    ):
        self.memory_store = memory_store
        self.recent_summary_store = recent_summary_store

    @staticmethod
    def size_hint(content: str) -> str:
        """Return a compact size hint for durable prompt documents."""
        return f"Approx size: {len(str(content or '')):,} chars. Keep this document concise; use search tools for detailed past transcripts."

    def load_documents(self, session_id: str) -> list[PromptMemoryDocument]:
        """Load durable memory documents that should be injected into the system prompt."""
        documents: list[PromptMemoryDocument] = []

        memory = self.memory_store.read(session_id)
        if memory:
            documents.append(PromptMemoryDocument(title="Memory", content=memory))

        recent_summary = self.recent_summary_store.read(session_id)
        if recent_summary:
            documents.append(PromptMemoryDocument(title="Recent Summary", content=recent_summary))

        return documents

    def build_prompt_sections(self, session_id: str) -> list[str]:
        """Return non-empty prompt sections for durable memory documents."""
        return [
            section
            for document in self.load_documents(session_id)
            if (section := document.render())
        ]
