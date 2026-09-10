"""Transactional expansion of provider identities without rewriting history."""

import sqlite3


OLD_CHECK = "CHECK(provider_id IN ('openai', 'anthropic', 'openrouter'))"
NEW_CHECK = "CHECK(provider_id IN ('openai', 'anthropic', 'openrouter') OR (length(provider_id) = 36 AND substr(provider_id, 15, 1) = '4'))"


def migrate_v15_to_v16(connection: sqlite3.Connection) -> None:
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        for table in ("runs", "conversation_compactions", "schedules"):
            row = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if row is None:
                raise ValueError("missing provider table")
            sql = row[0]
            if OLD_CHECK not in sql:
                continue
            indexes = [item[0] for item in connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (table,))]
            temporary = table + "_v16"
            declaration = sql[:sql.index("(")]
            replacement = sql.replace(declaration, f'CREATE TABLE "{temporary}" ', 1).replace(OLD_CHECK, NEW_CHECK)
            connection.execute(replacement)
            connection.execute(f'INSERT INTO "{temporary}" SELECT * FROM "{table}"')
            connection.execute(f'DROP TABLE "{table}"')
            connection.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
            for index in indexes:
                connection.execute(index)
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("provider migration integrity failure")
        connection.execute("PRAGMA user_version = 16")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute(f"PRAGMA foreign_keys = {int(foreign_keys)}")
