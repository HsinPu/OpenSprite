import asyncio
import json
import sqlite3

from typer.testing import CliRunner

from opensprite.cli.commands import app
from opensprite.search.sqlite_store import SQLiteSearchStore
from opensprite.storage.base import StoredMessage
from opensprite.storage.sqlite import SQLiteStorage


runner = CliRunner()


def _write_config(path, db_path, *, enabled=True, history_top_k=5):
    path.with_name("history_search.json").write_text(
        json.dumps(
            {
                "enabled": enabled,
                "history_top_k": history_top_k,
            }
        ),
        encoding="utf-8",
    )
    path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "key",
                    "model": "gpt",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
                "storage": {"type": "sqlite", "path": str(db_path)},
                "channels": {
                    "instances": {
                        "telegram": {"type": "telegram", "enabled": False},
                        "web": {"type": "web", "enabled": True},
                    }
                },
                "history_search_file": "history_search.json",
            }
        ),
        encoding="utf-8",
    )


def _open_live_wal_with_search_row(db_path):
    SQLiteStorage(db_path)
    writer = sqlite3.connect(str(db_path))
    try:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute(
            "INSERT INTO chats (session_id, created_at, updated_at) VALUES (?, ?, ?)",
            ("chat-live", 10.0, 10.0),
        )
        message_id = int(
            writer.execute(
                """
                INSERT INTO messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                ("chat-live", "user", "live WAL content", 10.0),
            ).lastrowid
        )
        writer.execute(
            """
            INSERT INTO search_chunks (
                session_id,
                message_id,
                role,
                chunk_index,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("chat-live", message_id, "user", 0, "live WAL content", 10.0),
        )
        writer.commit()
        return writer
    except Exception:
        writer.close()
        raise


def test_status_command_renders_history_search_values(tmp_path):
    db_path = tmp_path / "sessions.db"
    config_path = tmp_path / "opensprite.json"
    _write_config(config_path, db_path, history_top_k=7)

    result = runner.invoke(app, ["status", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "History search: enabled=yes (history_top_k=7)" in result.stdout


def test_search_status_cli_reports_plain_fts_counts(tmp_path):
    db_path = tmp_path / "sessions.db"
    config_path = tmp_path / "opensprite.json"
    _write_config(config_path, db_path)

    async def scenario():
        storage = SQLiteStorage(db_path)
        search = SQLiteSearchStore(db_path)
        await storage.add_message(
            "chat-a",
            StoredMessage(role="user", content="Please keep sqlite docs handy", timestamp=10.0),
        )
        await search.index_message(
            "chat-a",
            role="user",
            content="Please keep sqlite docs handy",
            created_at=10.0,
        )

    asyncio.run(scenario())
    result = runner.invoke(app, ["search", "status", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Chat history search status for all sessions." in result.stdout
    assert "Backend: SQLite FTS5" in result.stdout
    assert "Messages: 1" in result.stdout
    assert "Chunks: 1" in result.stdout
    assert "Embedding" not in result.stdout
    assert "Queue worker" not in result.stdout


def test_search_status_missing_config_does_not_create_files(tmp_path):
    config_path = tmp_path / "missing" / "opensprite.json"

    result = runner.invoke(app, ["search", "status", "--config", str(config_path)])

    assert result.exit_code == 1
    assert not config_path.parent.exists()


def test_search_status_missing_database_does_not_create_parent(tmp_path):
    db_path = tmp_path / "data" / "sessions.db"
    config_path = tmp_path / "opensprite.json"
    _write_config(config_path, db_path)

    result = runner.invoke(app, ["search", "status", "--config", str(config_path)])

    assert result.exit_code == 1
    assert not db_path.parent.exists()


def test_search_status_does_not_migrate_or_modify_existing_database(tmp_path):
    db_path = tmp_path / "sessions.db"
    config_path = tmp_path / "opensprite.json"
    _write_config(config_path, db_path)
    SQLiteStorage(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    finally:
        conn.close()

    before_bytes = db_path.read_bytes()
    before_entries = {path.name for path in tmp_path.iterdir()}

    result = runner.invoke(app, ["search", "status", "--config", str(config_path)])

    assert result.exit_code == 0
    assert db_path.read_bytes() == before_bytes
    assert {path.name for path in tmp_path.iterdir()} == before_entries
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        conn.close()


def test_search_status_reads_live_wal_without_modifying_source_files(tmp_path):
    db_path = tmp_path / "sessions.db"
    config_path = tmp_path / "opensprite.json"
    _write_config(config_path, db_path)
    writer = _open_live_wal_with_search_row(db_path)
    try:
        source_paths = (
            db_path,
            db_path.with_name(f"{db_path.name}-wal"),
            db_path.with_name(f"{db_path.name}-shm"),
        )
        assert all(path.is_file() for path in source_paths)
        before = {
            path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in source_paths
        }

        result = runner.invoke(
            app,
            ["search", "status", "--config", str(config_path)],
        )

        assert result.exit_code == 0
        assert "Messages: 1" in result.stdout
        assert "Chunks: 1" in result.stdout
        assert {
            path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in source_paths
        } == before
    finally:
        writer.close()


def test_search_status_recovers_wal_without_source_shm(tmp_path):
    source_path = tmp_path / "source.db"
    recovery_path = tmp_path / "recovery.db"
    config_path = tmp_path / "opensprite.json"
    writer = _open_live_wal_with_search_row(source_path)
    try:
        source_wal_path = source_path.with_name(f"{source_path.name}-wal")
        recovery_wal_path = recovery_path.with_name(f"{recovery_path.name}-wal")
        recovery_path.write_bytes(source_path.read_bytes())
        recovery_wal_path.write_bytes(source_wal_path.read_bytes())
    finally:
        writer.close()

    _write_config(config_path, recovery_path)
    before = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (recovery_path, recovery_wal_path)
    }

    result = runner.invoke(
        app,
        ["search", "status", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "Messages: 1" in result.stdout
    assert "Chunks: 1" in result.stdout
    assert not recovery_path.with_name(f"{recovery_path.name}-shm").exists()
    assert {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (recovery_path, recovery_wal_path)
    } == before


def test_search_status_reports_corrupt_database_accurately(tmp_path):
    db_path = tmp_path / "corrupt.db"
    config_path = tmp_path / "opensprite.json"
    db_path.write_bytes(b"not a sqlite database")
    _write_config(config_path, db_path)

    result = runner.invoke(
        app,
        ["search", "status", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    output = result.stdout + result.stderr
    assert "unavailable or incompatible" in output
    assert "changed while creating" not in output


def test_search_help_only_exposes_status_command():
    result = runner.invoke(app, ["search", "--help"])

    assert result.exit_code == 0
    assert "status" in result.stdout
    assert "rebuild" not in result.stdout
