import sqlite3
import pytest

from opensprite_backend.conversations.compaction_event_migration import migrate


def test_migration_preserves_existing_events_and_accepts_terminal_events():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE run_events (run_id TEXT, sequence INTEGER, type TEXT CHECK(type IN ('context.compaction.started')), payload_json TEXT, created_at TEXT, PRIMARY KEY(run_id, sequence))")
    connection.execute("INSERT INTO run_events VALUES ('run', 1, 'context.compaction.started', '{}', 'now')")
    connection.commit()
    migrate(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 17
    assert connection.execute("SELECT payload_json FROM run_events WHERE sequence=1").fetchone()[0] == "{}"
    for sequence, suffix in enumerate(("completed", "failed", "cancelled"), 2):
        connection.execute("INSERT INTO run_events VALUES (?, ?, ?, ?, ?)", ("run", sequence, f"context.compaction.{suffix}", "{}", "now"))
    assert connection.execute("SELECT count(*) FROM run_events").fetchone()[0] == 4
    connection.close()


def test_migration_rolls_back_ddl_and_version_on_copy_failure():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE run_events (type TEXT CHECK(type IN ('context.compaction.started')))")
    connection.execute("INSERT INTO run_events VALUES ('context.compaction.started')")
    connection.execute("PRAGMA user_version=16")
    connection.commit()
    connection.set_authorizer(lambda action, arg1, *args: sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_INSERT and arg1 == "run_events" else sqlite3.SQLITE_OK)
    with pytest.raises(sqlite3.DatabaseError):
        migrate(connection)
    connection.set_authorizer(None)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 16
    assert connection.execute("SELECT type FROM run_events").fetchall() == [("context.compaction.started",)]
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='run_events_v16'").fetchall() == []
    connection.close()
