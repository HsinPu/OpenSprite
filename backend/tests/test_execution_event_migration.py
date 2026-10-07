"""Schema 19 execution history survives the plugin-metadata migration."""

from __future__ import annotations

from contextlib import closing
import sqlite3
from uuid import uuid4

import pytest

from opensprite_backend.conversations.execution_event_migration import migrate
from opensprite_backend.conversations.models import RunEventType, RunStatus, StoreFailure
from opensprite_backend.conversations.repository import ConversationStoreError
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.conversations.sqlite_schema import SCHEMA_SQL


PROFILE = {
    "loopId": "standard", "loopVersion": "1.0.0",
    "policyId": "no_recovery", "policyVersion": "1.0.0", "apiVersion": 1,
}


def start(repository, *, conversation_id=None, message="Keep this user message", request_id=None):
    return repository.start_run(conversation_id=conversation_id,
                                client_request_id=request_id or str(uuid4()), message=message,
                                provider_id="openrouter", model_id="openrouter/auto", response_mode="default")


def table_rows(connection):
    tables = [item[0] for item in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {table: connection.execute(f'SELECT * FROM "{table}"').fetchall() for table in tables}


def test_repository_upgrades_real_schema_19_without_changing_runs_messages_or_events(tmp_path):
    source_path = tmp_path / "source.sqlite"
    source = SqliteConversationRepository(source_path)
    request_id = str(uuid4())
    completed = start(source, request_id=request_id)
    source.mark_run_started(completed.run.id)
    source.append_assistant_delta(completed.run.id, "completed answer")
    source.complete_run(completed.run.id, "completed answer")
    running = start(source, conversation_id=completed.conversation.id, message="Keep this active request")
    source.mark_run_started(running.run.id)
    source.append_assistant_delta(running.run.id, "durable partial answer")

    legacy_path = tmp_path / "legacy.sqlite"
    legacy_sql = SCHEMA_SQL.replace("'run.started', 'execution.selected'", "'run.started'").replace(
        "PRAGMA user_version = 20;", "PRAGMA user_version = 19;")
    assert legacy_sql != SCHEMA_SQL and "'execution.selected'" not in legacy_sql
    with closing(sqlite3.connect(source_path)) as original, closing(sqlite3.connect(legacy_path, isolation_level=None)) as legacy:
        legacy.executescript(legacy_sql)
        legacy.execute("PRAGMA foreign_keys = ON")
        before = table_rows(original)
        for table, rows in before.items():
            for row in rows:
                placeholders = ",".join("?" for _ in row)
                legacy.execute(f'INSERT INTO "{table}" VALUES ({placeholders})', row)
        assert legacy.execute("PRAGMA user_version").fetchone()[0] == 19
        assert table_rows(legacy) == before
        assert legacy.execute("PRAGMA foreign_key_check").fetchall() == []

    upgraded = SqliteConversationRepository(legacy_path)
    upgraded.ensure_schema()
    with closing(sqlite3.connect(legacy_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 20
        assert table_rows(connection) == before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='run_events_v19'").fetchall() == []
    assert upgraded.get_run(completed.run.id).status is RunStatus.COMPLETED
    assert upgraded.get_run(running.run.id).status is RunStatus.RUNNING
    assert upgraded.get_run(running.run.id).partial_text == "durable partial answer"
    replay = start(upgraded, request_id=request_id)
    assert replay.replayed and replay.run.id == completed.run.id
    event = upgraded.append_run_event(running.run.id, RunEventType.EXECUTION_SELECTED, PROFILE)
    assert event.data == PROFILE
    assert upgraded.list_run_events(running.run.id, after_sequence=event.sequence - 1, limit=10) == (event,)


@pytest.mark.parametrize("payload", [
    {**PROFILE, "credential": "must never enter event history"},
    {key: value for key, value in PROFILE.items() if key != "loopVersion"},
    {**PROFILE, "apiVersion": True},
    {**PROFILE, "apiVersion": 2},
    {**PROFILE, "apiVersion": "1"},
    {**PROFILE, "loopId": "../plugin"},
    {**PROFILE, "loopId": "Standard"},
    {**PROFILE, "loopId": "a" * 65},
    {**PROFILE, "policyId": "no recovery"},
    {**PROFILE, "policyId": None},
    {**PROFILE, "policyId": 1},
    {**PROFILE, "loopVersion": ""},
    {**PROFILE, "policyVersion": "x" * 65},
])
def test_execution_event_validator_rejects_unapproved_fields_and_invalid_identity(tmp_path, payload):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    accepted = start(repository)
    repository.mark_run_started(accepted.run.id)
    before = repository.list_run_events(accepted.run.id, after_sequence=0, limit=100)
    with pytest.raises(ConversationStoreError) as failure:
        repository.append_run_event(accepted.run.id, RunEventType.EXECUTION_SELECTED, payload)
    assert failure.value.failure is StoreFailure.INVALID_REQUEST
    assert repository.list_run_events(accepted.run.id, after_sequence=0, limit=100) == before
    assert repository.get_run(accepted.run.id).status is RunStatus.RUNNING
    valid = repository.append_run_event(accepted.run.id, RunEventType.EXECUTION_SELECTED, PROFILE)
    assert valid.sequence == before[-1].sequence + 1


def test_migration_rejects_an_unrecognized_event_constraint_without_advancing_version():
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE run_events (type TEXT CHECK(type IN ('tool.started')), payload_json TEXT)")
        connection.execute("INSERT INTO run_events VALUES ('tool.started', '{\"kept\":true}')")
        connection.execute("PRAGMA user_version = 19")
        connection.commit()
        before = connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
        with pytest.raises(sqlite3.DatabaseError):
            migrate(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 19
        assert connection.execute("SELECT * FROM run_events").fetchall() == [("tool.started", '{"kept":true}')]
        assert connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall() == before
        assert not connection.in_transaction


def test_copy_failure_rolls_back_table_rebuild_existing_events_and_schema_version():
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE run_events (type TEXT CHECK(type IN ('run.started')), payload_json TEXT)")
        connection.execute("INSERT INTO run_events VALUES ('run.started', '{\"kept\":true}')")
        connection.execute("PRAGMA user_version = 19")
        connection.commit()
        connection.execute("PRAGMA foreign_keys = ON")
        before = connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
        connection.set_authorizer(lambda action, table, *arguments: sqlite3.SQLITE_DENY
                                  if action == sqlite3.SQLITE_INSERT and table == "run_events" else sqlite3.SQLITE_OK)
        with pytest.raises(sqlite3.DatabaseError):
            migrate(connection)
        connection.set_authorizer(None)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 19
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("SELECT * FROM run_events").fetchall() == [("run.started", '{"kept":true}')]
        assert connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall() == before
        assert not connection.in_transaction
