"""Actual legacy-schema upgrade, step pagination and cancellation races."""
import asyncio
from contextlib import closing
from pathlib import Path
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from test_agent_loop import store, accepted_run, seed_completed_turns
from test_agent_chat_service import service
from opensprite_backend.app import create_app
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.conversations.sqlite_schema import migrate_schema
from opensprite_backend.conversations.models import PublicRunError, RunStatus


@pytest.mark.parametrize("version", [21, 22])
def test_actual_legacy_schema_preserves_all_raw_rows_and_summary_provenance(tmp_path, version):
    source = store(tmp_path / "source")
    conversation = seed_completed_turns(source, 2, assistant_size=30)
    source.append_compaction(conversation_id=conversation, covers_through_sequence=2,
        summary="legacy summary", source_hash="a"*64, provider_id="openrouter",
        model_id="fixture", input_tokens=10, output_tokens=4)
    target = tmp_path / "legacy.sqlite"
    with closing(sqlite3.connect(source.database_file)) as original, closing(sqlite3.connect(target)) as old:
        original.row_factory = sqlite3.Row
        old.executescript((Path(__file__).parent / f"fixtures/core_schema_v{version}.sql").read_text())
        before = {}
        for table in ("conversations", "messages", "runs", "conversation_compactions", "run_events"):
            columns = [row[1] for row in old.execute(f"PRAGMA table_info({table})")]
            rows = [tuple("5" if column == "output_continuation" else row[column] for column in columns) for row in original.execute(f"SELECT * FROM {table}")]
            old.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", rows)
            before[table] = (columns, rows)
        old.commit()
    repository = SqliteConversationRepository(target)
    # Open the real writer to migrate without a new Run legitimately updating
    # the conversation title/revision used by the preservation assertion.
    with closing(repository._open_write()):
        pass
    with closing(sqlite3.connect(target)) as upgraded:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == 23
        assert upgraded.execute("PRAGMA foreign_key_check").fetchall() == []
        for table, (columns, rows) in before.items():
            assert all(row in upgraded.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall() for row in rows)
    summary = repository.get_latest_compaction(conversation)
    assert (summary.summary, summary.producer_plugin_id, summary.producer_plugin_version, summary.summary_format) == (
        "legacy summary", "legacy", "unknown", "opensprite.text.v1")


def test_failed_mid_migration_rolls_back_tables_version_and_rows():
    with closing(sqlite3.connect(":memory:")) as db:
        sql = (Path(__file__).parent / "fixtures/core_schema_v21.sql").read_text()
        sql = sql.replace("UNIQUE(conversation_id, covers_through_sequence)", "UNIQUE(conversation_id, source_hash)")
        db.executescript(sql)
        original = db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        with pytest.raises(ValueError, match="compaction schema"): migrate_schema(db)
        assert db.execute("PRAGMA user_version").fetchone()[0] == 21
        assert db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall() == original


def test_restart_interrupts_private_step_without_exposing_draft(tmp_path):
    repository = store(tmp_path)
    run = accepted_run(repository)
    repository.mark_run_started(run.id)
    step = repository.start_step(run.id, label="draft", channel="draft")
    repository.append_step_delta(step.id, "kept private")
    assert repository.interrupt_incomplete_runs() == (run.id,)
    assert repository.get_run(run.id).status is RunStatus.INTERRUPTED
    assert repository.get_run(run.id).partial_text == ""
    saved = repository.list_run_steps(run.id)[0]
    assert saved.status == "interrupted" and saved.text == "kept private"


def test_steps_endpoint_uses_real_repository_pagination_and_bounds(tmp_path):
    chat, repository, manager, _ = service(tmp_path)
    run = accepted_run(repository)
    repository.mark_run_started(run.id)
    for index in range(103):
        step = repository.start_step(run.id, label=f"fixture-{index}", channel="draft")
        repository.append_step_delta(step.id, "private "+str(index))
        repository.finish_step(step.id, status="completed", finish_reason="final")
    with TestClient(create_app(agent_chat=chat)) as browser:
        first = browser.get(f"/api/runs/{run.id}/steps").json()
        assert len(first["steps"]) == 100 and first["nextAfterSequence"] == 100
        second = browser.get(f"/api/runs/{run.id}/steps?afterSequence=100").json()
        assert [item["sequence"] for item in second["steps"]] == [101,102,103]
        assert second["nextAfterSequence"] is None and second["steps"][-1]["text"] == "private 102"
        assert first["steps"][0]["runId"] == run.id
        for query in ("limit=101","limit=0","afterSequence=-1","afterSequence=9007199254740992"):
            assert browser.get(f"/api/runs/{run.id}/steps?{query}").status_code == 400
        assert browser.get(f"/api/runs/{uuid4()}/steps").status_code == 404
    asyncio.run(chat.close())


def test_steps_endpoint_requires_authentication(tmp_path):
    class RejectAuthentication:
        async def authenticate(self, token): return None
    chat, _, _, _ = service(tmp_path)
    with TestClient(create_app(agent_chat=chat, enforce_authentication=True,
        local_authentication=RejectAuthentication())) as browser:
        response = browser.get(f"/api/runs/{uuid4()}/steps")
        assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
        assert "steps" not in response.json()
    asyncio.run(chat.close())
