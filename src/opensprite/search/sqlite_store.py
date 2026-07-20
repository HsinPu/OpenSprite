"""SQLite FTS5 index for local conversation-history search."""

from __future__ import annotations

import asyncio
import hashlib
import re
import sqlite3
import tempfile
import time
import unicodedata
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
MAX_HISTORY_SEARCH_QUERY_LENGTH = 512
MAX_HISTORY_SEARCH_QUERY_TOKENS = 64
_READ_ONLY_SNAPSHOT_ATTEMPTS = 3
_SNAPSHOT_COPY_BUFFER_SIZE = 1024 * 1024
_LITERAL_IDENTIFIER_TERM_PATTERN = re.compile(
    r"(?<![\w+#])(?P<identifier>\w+(?:\+\+|#)\w*)(?![\w+#])",
    flags=re.UNICODE,
)


class _ReadOnlySnapshotConnection(sqlite3.Connection):
    """SQLite connection that owns and removes its private snapshot."""

    _snapshot_directory: tempfile.TemporaryDirectory | None = None

    def attach_snapshot_directory(
        self,
        snapshot_directory: tempfile.TemporaryDirectory,
    ) -> None:
        self._snapshot_directory = snapshot_directory

    def close(self) -> None:
        try:
            super().close()
        finally:
            snapshot_directory = self._snapshot_directory
            self._snapshot_directory = None
            if snapshot_directory is not None:
                try:
                    snapshot_directory.cleanup()
                except OSError as exc:
                    raise RuntimeError(
                        "could not clean up the read-only history search snapshot"
                    ) from exc


class _SnapshotChangedError(RuntimeError):
    """Internal signal that a source database changed during capture."""


def _cleanup_snapshot_attempt(
    conn: _ReadOnlySnapshotConnection | None,
    snapshot_directory: tempfile.TemporaryDirectory | None,
) -> None:
    if conn is not None:
        conn.close()
        return
    if snapshot_directory is None:
        return
    try:
        snapshot_directory.cleanup()
    except OSError as exc:
        raise RuntimeError(
            "could not clean up the read-only history search snapshot"
        ) from exc


def _path_state(path: Path) -> tuple[int, int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _snapshot_source_state(
    db_path: Path,
    wal_path: Path,
    shm_path: Path,
) -> tuple[
    tuple[int, int, int] | None,
    tuple[int, int, int] | None,
    tuple[int, int, int] | None,
]:
    return (
        _path_state(db_path),
        _path_state(wal_path),
        _path_state(shm_path),
    )


def _copy_with_sha256(source: Path, destination: Path) -> bytes:
    digest = hashlib.sha256()
    with source.open("rb") as source_file, destination.open("wb") as destination_file:
        while chunk := source_file.read(_SNAPSHOT_COPY_BUFFER_SIZE):
            digest.update(chunk)
            destination_file.write(chunk)
    return digest.digest()


def _file_sha256(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(_SNAPSHOT_COPY_BUFFER_SIZE):
            digest.update(chunk)
    return digest.digest()


def _unicode_casefold(value: str | None) -> str:
    normalized = unicodedata.normalize("NFC", value or "")
    return unicodedata.normalize("NFC", normalized.casefold())


def _literal_identifiers(query: str) -> list[str]:
    normalized_query = unicodedata.normalize("NFC", query)
    identifiers: list[str] = []
    seen: set[str] = set()
    for match in _LITERAL_IDENTIFIER_TERM_PATTERN.finditer(normalized_query):
        identifier = match.group("identifier")
        normalized_identifier = _unicode_casefold(identifier)
        if normalized_identifier in seen:
            continue
        seen.add(normalized_identifier)
        identifiers.append(identifier)
    return identifiers


def _query_without_literal_identifiers(query: str) -> str:
    normalized_query = unicodedata.normalize("NFC", query)
    return _LITERAL_IDENTIFIER_TERM_PATTERN.sub(" ", normalized_query)


def _deduplicated_query_tokens(query: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"\w+", query.lower()):
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def parse_history_search_terms(query: str) -> tuple[list[str], list[str]]:
    """Split a query into semantic literals and ordinary word tokens."""
    literals = _literal_identifiers(query)
    tokens = _deduplicated_query_tokens(_query_without_literal_identifiers(query))
    return literals, tokens


def _is_contiguous_script_character(character: str) -> bool:
    unicode_name = unicodedata.name(character, "")
    return unicode_name.startswith(
        (
            "CJK COMPATIBILITY IDEOGRAPH",
            "CJK UNIFIED IDEOGRAPH",
            "HANGUL",
            "HIRAGANA",
            "KATAKANA",
        )
    )


def _unicode_search_spans(value: str | None) -> list[tuple[str, str]]:
    normalized_value = _unicode_casefold(value)
    spans: list[tuple[str, str]] = []
    current_kind: str | None = None
    for character in normalized_value:
        if _is_contiguous_script_character(character):
            kind = "contiguous"
        elif character.isalnum() or character == "_":
            kind = "word"
        elif unicodedata.category(character).startswith("M") and current_kind:
            kind = current_kind
        else:
            current_kind = None
            continue

        if spans and current_kind == kind:
            previous_kind, previous_text = spans[-1]
            spans[-1] = (previous_kind, f"{previous_text}{character}")
        else:
            spans.append((kind, character))
        current_kind = kind
    return spans


def _unicode_search_span_matches(
    query_kind: str,
    query_text: str,
    content_kind: str,
    content_text: str,
    *,
    has_previous_query_span: bool,
    has_next_query_span: bool,
) -> bool:
    if query_kind != content_kind:
        return False
    if query_kind != "contiguous":
        return query_text == content_text
    if has_previous_query_span and has_next_query_span:
        return query_text == content_text
    if has_previous_query_span:
        return content_text.startswith(query_text)
    if has_next_query_span:
        return content_text.endswith(query_text)
    return query_text in content_text


def _matching_unicode_span_index(
    content_spans: list[tuple[str, str]],
    query_spans: list[tuple[str, str]],
) -> int | None:
    if len(query_spans) > len(content_spans):
        return None

    for start in range(len(content_spans) - len(query_spans) + 1):
        candidates = content_spans[start : start + len(query_spans)]
        if all(
            _unicode_search_span_matches(
                query_kind,
                query_text,
                content_kind,
                content_text,
                has_previous_query_span=index > 0,
                has_next_query_span=index < len(query_spans) - 1,
            )
            for index, (
                (query_kind, query_text),
                (content_kind, content_text),
            ) in enumerate(zip(query_spans, candidates))
        ):
            return start
    return None


def find_history_search_token_offset(value: str, token: str) -> int | None:
    """Return a folded-text offset for one parsed ordinary query token."""
    query_spans = _unicode_search_spans(token)
    if not query_spans:
        return None
    content_spans = _unicode_search_spans(value)
    match_index = _matching_unicode_span_index(content_spans, query_spans)
    if match_index is None:
        return None

    folded_value = _unicode_casefold(value)
    content_offsets: list[int] = []
    cursor = 0
    for _, content_text in content_spans:
        content_offset = folded_value.find(content_text, cursor)
        if content_offset < 0:
            return None
        content_offsets.append(content_offset)
        cursor = content_offset + len(content_text)

    content_kind, content_text = content_spans[match_index]
    query_kind, query_text = query_spans[0]
    relative_offset = 0
    if query_kind == content_kind == "contiguous":
        relative_offset = (
            len(content_text) - len(query_text)
            if len(query_spans) > 1
            else content_text.find(query_text)
        )
    return content_offsets[match_index] + relative_offset


def _unicode_token_match(value: str | None, token: str | None) -> int:
    if value is None or token is None:
        return 0
    return int(find_history_search_token_offset(value, token) is not None)


def validate_history_search_query(query: str) -> str:
    """Return a stripped query or raise a stable validation error."""
    if not isinstance(query, str):
        raise ValueError("history search query must be a string")

    normalized = query.strip()
    if len(normalized) > MAX_HISTORY_SEARCH_QUERY_LENGTH:
        raise ValueError(
            "history search query must be at most "
            f"{MAX_HISTORY_SEARCH_QUERY_LENGTH} characters"
        )

    literals, tokens = parse_history_search_terms(normalized)
    query_components = {_unicode_casefold(identifier) for identifier in literals}
    query_components.update(_unicode_casefold(token) for token in tokens)
    token_count = len(query_components)
    if token_count > MAX_HISTORY_SEARCH_QUERY_TOKENS:
        raise ValueError(
            "history search query has too many unique tokens "
            f"(maximum {MAX_HISTORY_SEARCH_QUERY_TOKENS})"
        )
    return normalized


class SQLiteSearchStore(SearchStore):
    """Per-session conversation history backed only by SQLite FTS5."""

    def __init__(
        self,
        path: str | Path,
        history_top_k: int = 5,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
        *,
        read_only: bool = False,
    ) -> None:
        self.path = Path(path).expanduser()
        self.history_top_k = self._bounded_limit(history_top_k, default=5)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._read_only = read_only
        self._lock = asyncio.Lock()

        if self._read_only:
            if not self.path.is_file():
                raise FileNotFoundError(
                    f"history search database does not exist: {self.path}"
                )
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        try:
            ensure_sqlite_schema(conn)
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        if self._read_only:
            return self._open_read_only_snapshot_connection()
        conn = open_sqlite_connection(self.path)
        conn.create_function(
            "unicode_casefold",
            1,
            _unicode_casefold,
            deterministic=True,
        )
        conn.create_function(
            "unicode_token_match",
            2,
            _unicode_token_match,
            deterministic=True,
        )
        return conn

    def _open_read_only_snapshot_connection(self) -> sqlite3.Connection:
        """Open a stable private copy without letting SQLite touch source files."""
        resolved_path = self.path.resolve()
        wal_path = Path(f"{resolved_path}-wal")
        shm_path = Path(f"{resolved_path}-shm")
        last_error: Exception | None = None

        for _ in range(_READ_ONLY_SNAPSHOT_ATTEMPTS):
            snapshot_directory: tempfile.TemporaryDirectory | None = None
            conn: _ReadOnlySnapshotConnection | None = None
            try:
                snapshot_directory = tempfile.TemporaryDirectory(
                    prefix="opensprite-search-readonly-"
                )
                snapshot_path = Path(snapshot_directory.name) / resolved_path.name
                snapshot_wal_path = Path(f"{snapshot_path}-wal")
                before_state = _snapshot_source_state(
                    resolved_path,
                    wal_path,
                    shm_path,
                )
                if before_state[0] is None:
                    raise FileNotFoundError(
                        f"history search database does not exist: {resolved_path}"
                    )
                has_wal = before_state[1] is not None

                copied_hashes = [_copy_with_sha256(resolved_path, snapshot_path)]
                source_paths = [resolved_path]
                if has_wal:
                    copied_hashes.append(_copy_with_sha256(wal_path, snapshot_wal_path))
                    source_paths.append(wal_path)

                source_hashes = [_file_sha256(path) for path in source_paths]
                after_state = _snapshot_source_state(
                    resolved_path,
                    wal_path,
                    shm_path,
                )
                if before_state != after_state or copied_hashes != source_hashes:
                    raise _SnapshotChangedError(
                        "history search database changed during snapshot capture"
                    )

                query = "mode=ro" if has_wal else "mode=ro&immutable=1"
                uri = f"{snapshot_path.resolve().as_uri()}?{query}"
                conn = sqlite3.connect(
                    uri,
                    timeout=30.0,
                    uri=True,
                    factory=_ReadOnlySnapshotConnection,
                )
                conn.attach_snapshot_directory(snapshot_directory)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only = ON")
                conn.execute("PRAGMA busy_timeout = 30000")
                conn.create_function(
                    "unicode_casefold",
                    1,
                    _unicode_casefold,
                    deterministic=True,
                )
                conn.create_function(
                    "unicode_token_match",
                    2,
                    _unicode_token_match,
                    deterministic=True,
                )
                conn.execute("PRAGMA schema_version").fetchone()
                return conn
            except _SnapshotChangedError as exc:
                last_error = exc
                _cleanup_snapshot_attempt(conn, snapshot_directory)
            except FileNotFoundError as exc:
                if snapshot_directory is None:
                    raise RuntimeError(
                        "could not create a read-only history search snapshot"
                    ) from exc
                last_error = exc
                _cleanup_snapshot_attempt(conn, snapshot_directory)
            except sqlite3.DatabaseError as exc:
                _cleanup_snapshot_attempt(conn, snapshot_directory)
                raise RuntimeError(
                    "history search index is unavailable or incompatible"
                ) from exc
            except OSError as exc:
                _cleanup_snapshot_attempt(conn, snapshot_directory)
                raise RuntimeError(
                    "could not create a read-only history search snapshot"
                ) from exc

        raise RuntimeError(
            "history search database changed while creating a read-only snapshot"
        ) from last_error

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
        """Search one session by merging FTS and Unicode substring matches."""
        query = validate_history_search_query(query)
        if not query:
            return []
        requested_limit = self._bounded_limit(limit, default=self.history_top_k)

        async with self._lock:
            conn = self._get_conn()
            try:
                fts_rows = self._search_fts(
                    conn,
                    session_id=session_id,
                    query=query,
                    limit=requested_limit,
                )
                substring_rows = self._search_substring(
                    conn,
                    session_id=session_id,
                    query=query,
                    limit=requested_limit,
                )
                rows = self._merge_search_rows(
                    fts_rows,
                    substring_rows,
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
            except sqlite3.DatabaseError as exc:
                raise RuntimeError(
                    "history search index is unavailable or incompatible"
                ) from exc
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
    def _query_tokens(query: str) -> list[str]:
        normalized = validate_history_search_query(query)
        _, tokens = parse_history_search_terms(normalized)
        return tokens

    @classmethod
    def _compile_match_query(cls, query: str) -> str | None:
        tokens = cls._query_tokens(query)
        if not tokens:
            return None
        return " AND ".join(f'"{token}"' for token in tokens)

    @staticmethod
    def _merge_search_rows(
        fts_rows: list[sqlite3.Row],
        substring_rows: list[sqlite3.Row],
        *,
        limit: int,
    ) -> list[sqlite3.Row]:
        """Keep FTS relevance first, then add Unicode-only rows by recency."""
        merged_rows: list[sqlite3.Row] = []
        seen_message_ids: set[int] = set()
        for rows in (fts_rows, substring_rows):
            for row in rows:
                message_id = int(row["message_id"])
                if message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)
                merged_rows.append(row)
                if len(merged_rows) >= limit:
                    return merged_rows
        return merged_rows

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
        literals, _ = parse_history_search_terms(query)
        normalized_literals = [_unicode_casefold(identifier) for identifier in literals]
        literal_filters = "".join(
            "\n                      AND instr(unicode_casefold(c.content), ?) > 0"
            for _ in normalized_literals
        )
        try:
            return conn.execute(
                f"""
                WITH matches AS (
                    SELECT
                        c.id,
                        c.message_id,
                        c.session_id,
                        c.content,
                        c.created_at,
                        c.role,
                        c.tool_name,
                        bm25(search_chunks_fts) AS score
                    FROM search_chunks_fts
                    JOIN search_chunks c ON c.id = search_chunks_fts.rowid
                    WHERE search_chunks_fts MATCH ?
                      AND c.session_id = ?{literal_filters}
                ),
                ranked_matches AS (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (
                            PARTITION BY message_id
                            ORDER BY score ASC, id DESC
                        ) AS message_rank
                    FROM matches
                )
                SELECT
                    id, message_id, session_id, content, created_at, role, tool_name, score
                FROM ranked_matches
                WHERE message_rank = 1
                ORDER BY score ASC, created_at DESC, id DESC
                LIMIT ?
                """,
                (match_query, session_id, *normalized_literals, limit),
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
        literals, tokens = parse_history_search_terms(query)
        normalized_literals = [_unicode_casefold(identifier) for identifier in literals]
        normalized_tokens = [_unicode_casefold(token) for token in tokens]
        if not normalized_literals and not normalized_tokens:
            return []

        term_filters = [
            "instr(unicode_casefold(content), ?) > 0"
            for _ in normalized_literals
        ]
        term_filters.extend(
            "unicode_token_match(content, ?) = 1" for _ in normalized_tokens
        )
        return conn.execute(
            f"""
            WITH matches AS (
                SELECT
                    id,
                    message_id,
                    session_id,
                    content,
                    created_at,
                    role,
                    tool_name,
                    1.0 AS score
                FROM search_chunks
                WHERE session_id = ?
                  AND {' AND '.join(term_filters)}
            ),
            ranked_matches AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY message_id
                        ORDER BY created_at DESC, id DESC
                    ) AS message_rank
                FROM matches
            )
            SELECT id, message_id, session_id, content, created_at, role, tool_name, score
            FROM ranked_matches
            WHERE message_rank = 1
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (session_id, *normalized_literals, *normalized_tokens, limit),
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
