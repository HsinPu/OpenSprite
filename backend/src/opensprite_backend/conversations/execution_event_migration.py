"""Allow pinned execution metadata without changing existing event payloads."""

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'run_events'").fetchone()
        if row is None or "'run.started'" not in row[0]:
            raise sqlite3.DatabaseError("missing event schema")
        schema = row[0]
        if "'execution.selected'" not in schema:
            schema = schema.replace("'run.started'", "'run.started', 'execution.selected'")
        connection.execute("ALTER TABLE run_events RENAME TO run_events_v19")
        connection.execute(schema)
        connection.execute("INSERT INTO run_events SELECT * FROM run_events_v19")
        connection.execute("DROP TABLE run_events_v19")
        connection.execute("PRAGMA user_version = 20")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
