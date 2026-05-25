"""Shared search indexing helpers for SQLite-backed storage."""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class SearchChunkPayload:
    """Searchable chunk payload stored in the shared SQLite index."""

    source_type: str
    content: str
    created_at: float
    role: str | None = None
    tool_name: str | None = None
    query: str | None = None
    title: str | None = None
    url: str | None = None
    chunk_index: int = 0


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Normalize text and split it into overlapping chunks."""
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(end - chunk_overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def build_history_chunks(
    *,
    role: str,
    content: str,
    tool_name: str | None,
    created_at: float,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[SearchChunkPayload]:
    """Build history chunk payloads from one stored message."""
    return [
        SearchChunkPayload(
            source_type="history",
            role=role,
            tool_name=tool_name,
            content=chunk,
            chunk_index=chunk_index,
            created_at=created_at,
        )
        for chunk_index, chunk in enumerate(
            chunk_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        )
    ]
