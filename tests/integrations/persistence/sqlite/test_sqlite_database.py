"""Characterization tests for the shared SQLite database layer."""

import json
import sqlite3

from opensprite.core.contracts.persistence import StoredMessage
from opensprite.integrations.persistence.sqlite import database as sqlite_database


EXPECTED_SCHEMA_MANIFEST = [
    ("index", "idx_background_processes_owner_updated"),
    ("index", "idx_background_processes_state_updated"),
    ("index", "idx_messages_chat_created"),
    ("index", "idx_run_events_chat_created"),
    ("index", "idx_run_events_run_created"),
    ("index", "idx_run_file_changes_chat_path"),
    ("index", "idx_run_file_changes_run_created"),
    ("index", "idx_run_parts_chat_created"),
    ("index", "idx_run_parts_run_created"),
    ("index", "idx_runs_chat_created"),
    ("index", "idx_runs_status"),
    ("index", "idx_search_chunks_chat_created"),
    ("index", "idx_search_chunks_message"),
    ("table", "background_processes"),
    ("table", "chat_state"),
    ("table", "chats"),
    ("table", "messages"),
    ("table", "run_events"),
    ("table", "run_file_changes"),
    ("table", "run_parts"),
    ("table", "runs"),
    ("table", "search_chunks"),
    ("table", "search_chunks_fts"),
    ("table", "search_chunks_fts_config"),
    ("table", "search_chunks_fts_data"),
    ("table", "search_chunks_fts_docsize"),
    ("table", "search_chunks_fts_idx"),
    ("trigger", "search_chunks_ad"),
    ("trigger", "search_chunks_ai"),
    ("trigger", "search_chunks_au"),
]


def test_sqlite_connection_and_schema_preserve_runtime_contract(tmp_path):
    db_path = tmp_path / "sessions.db"
    conn = sqlite_database.open_sqlite_connection(db_path)
    try:
        sqlite_database.ensure_sqlite_schema(conn)

        manifest = [
            (str(row["type"]), str(row["name"]))
            for row in conn.execute(
                """
                SELECT type, name
                FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            ).fetchall()
        ]

        assert conn.row_factory is sqlite3.Row
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert sqlite_database.SQLITE_SCHEMA_VERSION == 15
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 15
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert manifest == EXPECTED_SCHEMA_MANIFEST
    finally:
        conn.close()


def test_sqlite_message_primitives_preserve_identity_and_unicode_metadata(tmp_path):
    conn = sqlite_database.open_sqlite_connection(tmp_path / "messages.db")
    try:
        sqlite_database.ensure_sqlite_schema(conn)
        first_id = sqlite_database.insert_message_row(
            conn,
            "web:chat-1",
            StoredMessage(
                role="user",
                content="重複內容",
                timestamp=10.0,
                metadata={"語言": "繁體中文", "emoji": "🧪"},
                is_consolidated=True,
            ),
        )
        second_id = sqlite_database.insert_message_row(
            conn,
            "web:chat-1",
            StoredMessage(role="user", content="重複內容", timestamp=20.0),
        )
        tool_id = sqlite_database.insert_message_row(
            conn,
            "web:chat-1",
            StoredMessage(
                role="user",
                content="重複內容",
                timestamp=20.0,
                tool_name="history_search",
            ),
        )
        sqlite_database.ensure_chat_row(
            conn,
            "web:chat-1",
            created_at=999.0,
            updated_at=30.0,
        )

        chat_row = conn.execute(
            "SELECT created_at, updated_at FROM chats WHERE session_id = ?",
            ("web:chat-1",),
        ).fetchone()
        first_row = conn.execute(
            "SELECT metadata_json, is_consolidated FROM messages WHERE id = ?",
            (first_id,),
        ).fetchone()

        assert (first_id, second_id, tool_id) == (1, 2, 3)
        assert tuple(chat_row) == (10.0, 30.0)
        assert "繁體中文" in first_row["metadata_json"]
        assert "🧪" in first_row["metadata_json"]
        assert json.loads(first_row["metadata_json"]) == {
            "語言": "繁體中文",
            "emoji": "🧪",
        }
        assert first_row["is_consolidated"] == 1
        assert sqlite_database.find_message_id(
            conn,
            session_id="web:chat-1",
            role="user",
            content="重複內容",
            tool_name=None,
            created_at=10.0,
        ) == first_id
        assert sqlite_database.find_message_id(
            conn,
            session_id="web:chat-1",
            role="user",
            content="重複內容",
            tool_name=None,
            created_at=999.0,
        ) == second_id
        assert sqlite_database.find_message_id(
            conn,
            session_id="web:chat-1",
            role="user",
            content="重複內容",
            tool_name="history_search",
            created_at=999.0,
        ) == tool_id
        assert sqlite_database.find_message_id(
            conn,
            session_id="web:chat-1",
            role="assistant",
            content="missing",
            tool_name=None,
            created_at=999.0,
        ) is None
    finally:
        conn.close()
