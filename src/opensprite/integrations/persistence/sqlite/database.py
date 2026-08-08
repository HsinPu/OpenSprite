"""Shared SQLite schema and message-row primitives."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from ....core.contracts.persistence import StoredMessage
from ....core.serialization import json_safe_value as json_safe

SQLITE_SCHEMA_VERSION = 15

SCHEMA_SCRIPT = """
CREATE TABLE IF NOT EXISTS chats (
    session_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_state (
    session_id TEXT PRIMARY KEY REFERENCES chats(session_id) ON DELETE CASCADE,
    consolidated_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES chats(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    is_consolidated INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_created
    ON messages(session_id, created_at, id);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chats(session_id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_runs_chat_created
    ON runs(session_id, created_at, run_id);

CREATE INDEX IF NOT EXISTS idx_runs_status
    ON runs(status, updated_at);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES chats(session_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_created
    ON run_events(run_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_run_events_chat_created
    ON run_events(session_id, created_at, id);

CREATE TABLE IF NOT EXISTS run_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES chats(session_id) ON DELETE CASCADE,
    part_type TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tool_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_parts_run_created
    ON run_parts(run_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_run_parts_chat_created
    ON run_parts(session_id, created_at, id);

CREATE TABLE IF NOT EXISTS run_file_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES chats(session_id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    path TEXT NOT NULL,
    action TEXT NOT NULL,
    before_sha256 TEXT,
    after_sha256 TEXT,
    before_content TEXT,
    after_content TEXT,
    diff TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_file_changes_run_created
    ON run_file_changes(run_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_run_file_changes_chat_path
    ON run_file_changes(session_id, path, created_at, id);

CREATE TABLE IF NOT EXISTS background_processes (
    process_session_id TEXT PRIMARY KEY,
    owner_session_id TEXT NOT NULL REFERENCES chats(session_id) ON DELETE CASCADE,
    owner_run_id TEXT,
    owner_channel TEXT,
    owner_external_chat_id TEXT,
    pid INTEGER,
    command TEXT NOT NULL,
    cwd TEXT,
    state TEXT NOT NULL,
    termination_reason TEXT,
    exit_code INTEGER,
    notify_mode TEXT NOT NULL DEFAULT 'agent_summary',
    output_tail TEXT NOT NULL DEFAULT '',
    output_path TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    started_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_background_processes_owner_updated
    ON background_processes(owner_session_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_background_processes_state_updated
    ON background_processes(state, updated_at);

CREATE TABLE IF NOT EXISTS search_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES chats(session_id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    role TEXT,
    tool_name TEXT,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE(message_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_search_chunks_chat_created
    ON search_chunks(session_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_search_chunks_message
    ON search_chunks(message_id, chunk_index);

CREATE VIRTUAL TABLE IF NOT EXISTS search_chunks_fts USING fts5(
    content,
    content='search_chunks',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS search_chunks_ai AFTER INSERT ON search_chunks BEGIN
    INSERT INTO search_chunks_fts(rowid, content)
    VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS search_chunks_ad AFTER DELETE ON search_chunks BEGIN
    INSERT INTO search_chunks_fts(search_chunks_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS search_chunks_au AFTER UPDATE ON search_chunks BEGIN
    INSERT INTO search_chunks_fts(search_chunks_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO search_chunks_fts(rowid, content)
    VALUES (new.id, new.content);
END;
"""


def open_sqlite_connection(db_path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection for the shared app database."""
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return conn


def ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Ensure the normalized schema exists."""
    conn.executescript(SCHEMA_SCRIPT)
    conn.execute(f"PRAGMA user_version = {SQLITE_SCHEMA_VERSION}")
    conn.commit()


def ensure_chat_row(
    conn: sqlite3.Connection,
    session_id: str,
    *,
    created_at: float,
    updated_at: float | None = None,
) -> None:
    """Ensure the chat metadata row exists before inserting related records."""
    current_updated_at = updated_at if updated_at is not None else created_at
    conn.execute(
        """
        INSERT INTO chats (session_id, created_at, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (session_id, created_at, current_updated_at),
    )


def insert_message_row(conn: sqlite3.Connection, session_id: str, message: StoredMessage) -> int:
    """Insert one stored message row and return its numeric id."""
    created_at = float(message.timestamp or time.time())
    ensure_chat_row(conn, session_id, created_at=created_at, updated_at=created_at)
    cursor = conn.execute(
        """
        INSERT INTO messages (session_id, role, content, tool_name, metadata_json, is_consolidated, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            message.role,
            message.content,
            message.tool_name,
            json.dumps(json_safe(message.metadata), ensure_ascii=False),
            1 if message.is_consolidated else 0,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def find_message_id(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    role: str,
    content: str,
    tool_name: str | None,
    created_at: float,
) -> int | None:
    """Resolve the latest message row id for a just-persisted message."""
    row = conn.execute(
        """
        SELECT id
        FROM messages
        WHERE session_id = ?
          AND role = ?
          AND content = ?
          AND created_at = ?
          AND ((tool_name IS NULL AND ? IS NULL) OR tool_name = ?)
        ORDER BY id DESC
        LIMIT 1
        """,
        (session_id, role, content, created_at, tool_name, tool_name),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    fallback = conn.execute(
        """
        SELECT id
        FROM messages
        WHERE session_id = ?
          AND role = ?
          AND content = ?
          AND ((tool_name IS NULL AND ? IS NULL) OR tool_name = ?)
        ORDER BY id DESC
        LIMIT 1
        """,
        (session_id, role, content, tool_name, tool_name),
    ).fetchone()
    return int(fallback["id"]) if fallback is not None else None
