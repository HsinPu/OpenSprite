import sqlite3

import pytest

from opensprite_backend.conversations.provider_id_migration import NEW_CHECK, OLD_CHECK, migrate_v15_to_v16
from opensprite_backend.conversations.sqlite_schema import SCHEMA_SQL
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from uuid import uuid4


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


def test_provider_migration_keeps_existing_conversation_and_run_rows(tmp_path):
    source_path = tmp_path / "source.db"
    repository = SqliteConversationRepository(source_path)
    accepted = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message="Keep this history",
        provider_id="openrouter", model_id="openrouter/auto", response_mode="default")
    repository.interrupt_incomplete_runs()
    source = sqlite3.connect(source_path)
    legacy = sqlite3.connect(tmp_path / "legacy.db", isolation_level=None)
    legacy.executescript(SCHEMA_SQL.replace(NEW_CHECK, OLD_CHECK).replace("user_version = 16", "user_version = 15"))
    tables = [row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    before = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        rows = source.execute(f"SELECT * FROM {quoted}").fetchall()
        before[table] = rows
        for row in rows:
            legacy.execute(f"INSERT INTO {quoted} VALUES ({','.join('?' for _ in row)})", row)
    assert any(row for row in before["runs"] if accepted.run.id in row)
    legacy.execute("PRAGMA foreign_keys = ON")
    migrate_v15_to_v16(legacy)
    for table, rows in before.items():
        quoted = '"' + table.replace('"', '""') + '"'
        assert legacy.execute(f"SELECT * FROM {quoted}").fetchall() == rows
    assert legacy.execute("PRAGMA foreign_key_check").fetchall() == []
    source.close()
    legacy.close()
