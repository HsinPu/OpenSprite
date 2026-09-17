"""Expand mode constraints while retaining immutable historical Run values."""

import sqlite3

OLD_CHECK = "CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep'))"
NEW_CHECK = "CHECK(response_mode IN ('default', 'fast', 'balanced', 'deep', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'))"
RESOLUTION_COLUMN = "reasoning_resolution_json TEXT CHECK(reasoning_resolution_json IS NULL OR length(reasoning_resolution_json) <= 512)"


def migrate(connection: sqlite3.Connection) -> None:
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        for table in ("runs", "schedules"):
            row = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if row is None or (OLD_CHECK not in row[0] and NEW_CHECK not in row[0]):
                raise ValueError("unexpected response mode schema")
            sql = row[0]
            if NEW_CHECK in sql:
                continue
            indexes = [item[0] for item in connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (table,))]
            temporary = table + "_v19"
            declaration = sql[:sql.index("(")]
            connection.execute(sql.replace(declaration, f'CREATE TABLE "{temporary}" ', 1).replace(OLD_CHECK, NEW_CHECK))
            connection.execute(f'INSERT INTO "{temporary}" SELECT * FROM "{table}"')
            connection.execute(f'DROP TABLE "{table}"')
            connection.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
            for index in indexes:
                connection.execute(index)
        if "reasoning_resolution_json" not in {row[1] for row in connection.execute("PRAGMA table_info(runs)")}:
            connection.execute("ALTER TABLE runs ADD COLUMN " + RESOLUTION_COLUMN)
        connection.execute("""UPDATE schedules SET response_mode = CASE response_mode
            WHEN 'default' THEN 'medium' WHEN 'fast' THEN 'low'
            WHEN 'balanced' THEN 'medium' WHEN 'deep' THEN 'high' ELSE response_mode END""")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("response mode migration integrity failure")
        connection.execute("PRAGMA user_version = 19")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute(f"PRAGMA foreign_keys = {int(foreign_keys)}")
