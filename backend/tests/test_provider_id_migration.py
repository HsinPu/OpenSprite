import sqlite3

import pytest

from opensprite_backend.conversations.provider_id_migration import NEW_CHECK, OLD_CHECK, migrate_v15_to_v16
from opensprite_backend.conversations.sqlite_schema import SCHEMA_SQL


def test_provider_migration_preserves_schema_and_rolls_back(tmp_path):
    connection = sqlite3.connect(tmp_path / "db", isolation_level=None)
    connection.executescript(SCHEMA_SQL.replace(NEW_CHECK, OLD_CHECK).replace("user_version = 16", "user_version = 15"))
    connection.execute("PRAGMA foreign_keys = ON")
    before = connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
    connection.set_authorizer(lambda action, arg1, arg2, db, source:
        sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_DROP_TABLE and arg1 == "conversation_compactions" else sqlite3.SQLITE_OK)
    with pytest.raises(sqlite3.DatabaseError):
        migrate_v15_to_v16(connection)
    connection.set_authorizer(None)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 15
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall() == before
    migrate_v15_to_v16(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 16
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert {row[0] for row in before} == {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    connection.close()
