"""Transactional v13 to v14 event-constraint expansion."""
import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("ALTER TABLE run_events RENAME TO run_events_v13")
        connection.execute("""CREATE TABLE run_events (
            run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            sequence INTEGER NOT NULL CHECK(sequence >= 1),
            type TEXT NOT NULL CHECK(type IN (
                'run.started', 'context.compaction.started', 'model.started',
                'response.continuation.started', 'assistant.delta',
                'tool.approval_requested', 'tool.approval_decided',
                'tool.started', 'tool.completed', 'tool.failed',
                'skill.loaded', 'skill.load_failed',
                'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted')),
            payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
            created_at TEXT NOT NULL,
            PRIMARY KEY(run_id, sequence)) STRICT""")
        connection.execute("INSERT INTO run_events SELECT * FROM run_events_v13")
        connection.execute("DROP TABLE run_events_v13")
        connection.execute("PRAGMA user_version = 14")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
