import sqlite3
from contextlib import closing

import pytest

from opensprite_backend.custom_agents.child_schema import migrate_v14_to_v15
from opensprite_backend.conversations.sqlite_schema import SCHEMA_SQL, migrate_schema


def connection():
    database = sqlite3.connect(":memory:", isolation_level=None)
    database.execute("PRAGMA foreign_keys = ON")
    database.execute("CREATE TABLE runs (id TEXT PRIMARY KEY) STRICT")
    database.execute("INSERT INTO runs VALUES ('parent')")
    database.execute("PRAGMA user_version = 14")
    return database


def test_child_schema_keeps_parent_and_has_no_conversation_storage():
    with closing(connection()) as database:
        migrate_v14_to_v15(database)
        assert database.execute("PRAGMA user_version").fetchone()[0] == 15
        assert database.execute("SELECT * FROM runs").fetchall() == [("parent",)]
        tables = {row[0] for row in database.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert tables == {"runs", "agent_executions", "agent_execution_events"}
        columns = {row[1] for row in database.execute("PRAGMA table_info(agent_executions)")}
        assert not columns & {"root", "path", "developer_instructions", "conversation_id"}


def test_child_schema_failure_rolls_back_all_new_tables():
    with closing(connection()) as database:
        database.execute("CREATE TABLE agent_execution_events (sentinel TEXT)")
        with pytest.raises(sqlite3.OperationalError):
            migrate_v14_to_v15(database)
        assert database.execute("PRAGMA user_version").fetchone()[0] == 14
        assert database.execute(
            "SELECT name FROM sqlite_master WHERE name='agent_executions'"
        ).fetchall() == []
        assert database.execute("SELECT * FROM runs").fetchall() == [("parent",)]


def test_current_schema_and_full_v14_upgrade_have_identical_child_tables():
    with closing(sqlite3.connect(":memory:", isolation_level=None)) as database:
        database.executescript(SCHEMA_SQL)
        expected = database.execute(
            "SELECT name, sql FROM sqlite_master WHERE name LIKE 'agent_%' ORDER BY name"
        ).fetchall()
        database.execute("DROP TABLE agent_execution_events")
        database.execute("DROP TABLE agent_executions")
        database.execute("PRAGMA user_version = 14")
        migrate_schema(database)
        actual = database.execute(
            "SELECT name, sql FROM sqlite_master WHERE name LIKE 'agent_%' ORDER BY name"
        ).fetchall()
        assert actual == expected
        assert database.execute("PRAGMA user_version").fetchone()[0] == 16
