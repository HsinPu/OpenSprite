"""Expand the event type constraint without rewriting event payloads."""

import sqlite3

OLD_TYPES = "'context.compaction.started'"
NEW_TYPES = "'context.compaction.started', 'context.compaction.completed', 'context.compaction.failed', 'context.compaction.cancelled'"


def migrate(connection: sqlite3.Connection, *, attempts: bool = False) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'run_events'").fetchone()
        if row is None or ("'model.started'" if attempts else OLD_TYPES) not in row[0]:
            raise sqlite3.DatabaseError("missing event schema")
        schema = row[0].replace("'model.started'", "'model.started', 'model.attempt'") if attempts else row[0].replace(OLD_TYPES, NEW_TYPES)
        connection.execute("ALTER TABLE run_events RENAME TO run_events_v16")
        connection.execute(schema)
        connection.execute("INSERT INTO run_events SELECT * FROM run_events_v16")
        connection.execute("DROP TABLE run_events_v16")
        connection.execute("PRAGMA user_version = 18" if attempts else "PRAGMA user_version = 17")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
