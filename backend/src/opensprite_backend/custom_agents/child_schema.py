"""Child execution storage, separate from sidebar conversations and messages."""

import sqlite3


CHILD_SCHEMA_STATEMENTS = (
    """CREATE TABLE agent_executions (
        id TEXT PRIMARY KEY,
        parent_run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        spawn_call_id TEXT NOT NULL,
        request_hash TEXT NOT NULL CHECK(length(request_hash) = 64),
        agent_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        agent_revision INTEGER NOT NULL CHECK(agent_revision >= 1),
        definition_hash TEXT NOT NULL CHECK(length(definition_hash) = 64),
        provider_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN (
            'queued', 'running', 'cancelling', 'completed', 'failed',
            'cancelled', 'interrupted', 'timed_out')),
        result_text TEXT NOT NULL DEFAULT '' CHECK(length(result_text) <= 1048576),
        error_code TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        UNIQUE(parent_run_id, spawn_call_id)
    ) STRICT""",
    """CREATE INDEX agent_executions_by_parent
        ON agent_executions(parent_run_id, created_at, id)""",
    """CREATE TABLE agent_execution_events (
        execution_id TEXT NOT NULL REFERENCES agent_executions(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL CHECK(sequence >= 1),
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL CHECK(length(payload_json) <= 65536),
        created_at TEXT NOT NULL,
        PRIMARY KEY(execution_id, sequence)
    ) STRICT""",
)


def migrate_v14_to_v15(connection: sqlite3.Connection) -> None:
    """Create all child storage atomically; leave v14 intact on any failure."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in CHILD_SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute("PRAGMA user_version = 15")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
