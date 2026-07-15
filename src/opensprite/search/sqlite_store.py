"""SQLite FTS5 index for local conversation-history search."""

from __future__ import annotations

import asyncio
import re
import sqlite3
import time
from pathlib import Path

from .base import HISTORY_SEARCH_TOOL_NAME, SearchHit, SearchStore
from .indexing import build_history_chunks
from ..storage.sqlite import (
    ensure_sqlite_schema,
    find_message_id,
    insert_search_chunks,
    open_sqlite_connection,
)
from ..utils.log import logger

MAX_HISTORY_SEARCH_RESULTS = 20


class SQLiteSearchStore(SearchStore):
    """Per-session conversation history backed only by SQLite FTS5."""

    def __init__(
        self,
        path: str | Path,
        history_top_k: int = 5,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
    ) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.history_top_k = self._bounded_limit(history_top_k, default=5)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._lock = asyncio.Lock()

        conn = self._get_conn()
        try:
            ensure_sqlite_schema(conn)
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        return open_sqlite_connection(self.path)

    async def sync_from_storage(self) -> None:
        """Rebuild when persisted messages and indexed messages are out of sync."""
        async with self._lock:
            conn = self._get_conn()
            try:
                ensure_sqlite_schema(conn)
                indexable_message_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM messages
                        WHERE TRIM(content) <> ''
                          AND (tool_name IS NULL OR tool_name <> ?)
                        """,
                        (HISTORY_SEARCH_TOOL_NAME,),
                    ).fetchone()[0]
                )
                indexed_message_count = int(
                    conn.execute(
                        "SELECT COUNT(DISTINCT message_id) FROM search_chunks"
                    ).fetchone()[0]
                )
            finally:
                conn.close()

        if indexable_message_count != indexed_message_count:
            logger.info(
                "history_search.sync | rebuilding messages={} indexed_messages={}",
                indexable_message_count,
                indexed_message_count,
            )
            await self.rebuild_index()

    async def index_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
        created_at: float | None = None,
    ) -> None:
        """Index one already-persisted message."""
        if tool_name == HISTORY_SEARCH_TOOL_NAME:
            return

        timestamp = created_at if created_at is not None else time.time()
        chunks = build_history_chunks(
            role=role,
            content=content,
            tool_name=tool_name,
            created_at=timestamp,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        if not chunks:
            return

        async with self._lock:
            conn = self._get_conn()
            try:
                message_id = find_message_id(
                    conn,
                    session_id=session_id,
                    role=role,
                    content=content,
                    tool_name=tool_name,
                    created_at=timestamp,
                )
                if message_id is None:
                    logger.warning(
                        "history_search.index | persisted message not found session_id={} role={}",
                        session_id,
                        role,
                    )
                    return
                insert_search_chunks(
                    conn,
                    session_id=session_id,
                    message_id=message_id,
                    chunks=chunks,
                )
                conn.commit()
            finally:
                conn.close()

    async def search_history(
        self,
        session_id: str,
        query: str,
        limit: int = 5,
    ) -> list[SearchHit]:
        """Search one session, falling back to substring matching when FTS finds nothing."""
        query = query.strip()
        if not query:
            return []
        requested_limit = self._bounded_limit(limit, default=self.history_top_k)

        async with self._lock:
            conn = self._get_conn()
            try:
                rows = self._search_fts(
                    conn,
                    session_id=session_id,
                    query=query,
                    limit=requested_limit,
                )
                if not rows:
                    rows = self._search_substring(
                        conn,
                        session_id=session_id,
                        query=query,
                        limit=requested_limit,
                    )
                return [self._row_to_hit(row) for row in rows]
            finally:
                conn.close()

    async def clear_session(self, session_id: str) -> None:
        """Remove indexed chunks for one session without deleting its messages."""
        async with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM search_chunks WHERE session_id = ?", (session_id,))
                conn.commit()
            finally:
                conn.close()

    async def rebuild_index(self, session_id: str | None = None) -> dict[str, int]:
        """Rebuild searchable chunks from persisted conversation messages."""
        async with self._lock:
            conn = self._get_conn()
            try:
                ensure_sqlite_schema(conn)
                conn.execute("BEGIN")
                if session_id is None:
                    conn.execute("DELETE FROM search_chunks")
                    rows = conn.execute(
                        """
                        SELECT id, session_id, role, content, tool_name, created_at
                        FROM messages
                        WHERE TRIM(content) <> ''
                          AND (tool_name IS NULL OR tool_name <> ?)
                        ORDER BY session_id ASC, id ASC
                        """,
                        (HISTORY_SEARCH_TOOL_NAME,),
                    ).fetchall()
                else:
                    conn.execute("DELETE FROM search_chunks WHERE session_id = ?", (session_id,))
                    rows = conn.execute(
                        """
                        SELECT id, session_id, role, content, tool_name, created_at
                        FROM messages
                        WHERE session_id = ?
                          AND TRIM(content) <> ''
                          AND (tool_name IS NULL OR tool_name <> ?)
                        ORDER BY id ASC
                        """,
                        (session_id, HISTORY_SEARCH_TOOL_NAME),
                    ).fetchall()

                message_count = 0
                chunk_count = 0
                sessions: set[str] = set()
                for row in rows:
                    chunks = build_history_chunks(
                        role=str(row["role"]),
                        content=str(row["content"]),
                        tool_name=row["tool_name"],
                        created_at=float(row["created_at"] or 0),
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                    )
                    if not chunks:
                        continue
                    current_session_id = str(row["session_id"])
                    insert_search_chunks(
                        conn,
                        session_id=current_session_id,
                        message_id=int(row["id"]),
                        chunks=chunks,
                    )
                    sessions.add(current_session_id)
                    message_count += 1
                    chunk_count += len(chunks)

                conn.commit()
                return {
                    "session_count": len(sessions),
                    "message_count": message_count,
                    "chunk_count": chunk_count,
                }
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    async def get_status(self, session_id: str | None = None) -> dict[str, int]:
        """Return compact index counts for diagnostics."""
        async with self._lock:
            conn = self._get_conn()
            try:
                if session_id is None:
                    row = conn.execute(
                        """
                        SELECT
                            COUNT(DISTINCT session_id) AS session_count,
                            COUNT(DISTINCT message_id) AS message_count,
                            COUNT(*) AS chunk_count
                        FROM search_chunks
                        """
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT
                            COUNT(DISTINCT session_id) AS session_count,
                            COUNT(DISTINCT message_id) AS message_count,
                            COUNT(*) AS chunk_count
                        FROM search_chunks
                        WHERE session_id = ?
                        """,
                        (session_id,),
                    ).fetchone()
                return {
                    "session_count": int(row["session_count"] or 0),
                    "message_count": int(row["message_count"] or 0),
                    "chunk_count": int(row["chunk_count"] or 0),
                }
            finally:
                conn.close()

    @staticmethod
    def _bounded_limit(value: int | None, *, default: int) -> int:
        try:
            parsed = int(value if value is not None else default)
        except (TypeError, ValueError):
            parsed = default
        return min(max(parsed, 1), MAX_HISTORY_SEARCH_RESULTS)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join((text or "").lower().split())

    @staticmethod
    def _query_tokens(query: str) -> list[str]:
        return [token for token in re.findall(r"\w+", query.casefold()) if token]

    @classmethod
    def _compile_match_query(cls, query: str) -> str | None:
        tokens = cls._query_tokens(query)
        if not tokens:
            return None
        return " AND ".join(f'"{token}"' for token in tokens)

    @classmethod
    def _search_fts(
        cls,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        query: str,
        limit: int,
    ) -> list[sqlite3.Row]:
        match_query = cls._compile_match_query(query)
        if match_query is None:
            return []
        try:
            return conn.execute(
                """
                SELECT
                    c.id,
                    c.session_id,
                    c.content,
                    c.created_at,
                    c.role,
                    c.tool_name,
                    bm25(search_chunks_fts) AS score
                FROM search_chunks_fts
                JOIN search_chunks c ON c.id = search_chunks_fts.rowid
                WHERE search_chunks_fts MATCH ?
                  AND c.session_id = ?
                ORDER BY score ASC, c.created_at DESC, c.id DESC
                LIMIT ?
                """,
                (match_query, session_id, limit),
            ).fetchall()
        except sqlite3.DatabaseError:
            return []

    @classmethod
    def _search_substring(
        cls,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        query: str,
        limit: int,
    ) -> list[sqlite3.Row]:
        normalized_query = cls._normalize_text(query)
        if normalized_query:
            exact_rows = conn.execute(
                """
                SELECT
                    id,
                    session_id,
                    content,
                    created_at,
                    role,
                    tool_name,
                    2.0 AS score
                FROM search_chunks
                WHERE session_id = ?
                  AND instr(lower(content), ?) > 0
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (session_id, normalized_query, limit),
            ).fetchall()
            if exact_rows:
                return exact_rows

        query_tokens = cls._query_tokens(query)
        if not query_tokens:
            return []

        token_filters = " AND ".join(
            "instr(lower(content), ?) > 0" for _ in query_tokens
        )
        return conn.execute(
            f"""
            SELECT
                id,
                session_id,
                content,
                created_at,
                role,
                tool_name,
                1.0 AS score
            FROM search_chunks
            WHERE session_id = ?
              AND {token_filters}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (session_id, *query_tokens, limit),
        ).fetchall()

    @staticmethod
    def _row_to_hit(row: sqlite3.Row) -> SearchHit:
        score = row["score"]
        return SearchHit(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            content=str(row["content"]),
            created_at=float(row["created_at"] or 0),
            score=float(score) if score is not None else None,
            role=str(row["role"]) if row["role"] is not None else None,
            tool_name=(
                str(row["tool_name"])
                if row["tool_name"] is not None
                else None
            ),
        )
