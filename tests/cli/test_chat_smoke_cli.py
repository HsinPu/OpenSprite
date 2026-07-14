import asyncio
import json
import sqlite3

import pytest
from typer.testing import CliRunner

from opensprite.cli import commands
from opensprite.cli.commands_chat_smoke import (
    SmokeCase,
    check_trace,
    load_trace_readonly,
    resolve_external_chat_prefix,
    run_smoke_cases,
    select_cases,
    summarize_trace,
)
from opensprite.cli.commands_trace import trace_payload
from opensprite.runs.events import (
    TOOL_RESULT_EVENT,
    TOOL_STARTED_EVENT,
)
from opensprite.storage.base import StoredRun, StoredRunEvent, StoredRunPart, StoredRunTrace


def _completed_trace_summary(**overrides):
    summary = {
        "run_id": "run-1",
        "run_status": "completed",
        "persisted": True,
        "tools": [],
    }
    summary.update(overrides)
    return summary


def test_summarize_trace_extracts_run_and_tool_results():
    trace = StoredRunTrace(
        run=StoredRun(
            run_id="run-1",
            session_id="web:smoke",
            status="completed",
            created_at=1.0,
            updated_at=2.0,
        ),
        events=[
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type=TOOL_STARTED_EVENT,
                payload={"tool_name": "web_research"},
            ),
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type=TOOL_RESULT_EVENT,
                payload={"tool_name": "web_fetch", "ok": False},
            ),
        ],
    )

    summary = summarize_trace(trace)

    assert summary["run_id"] == "run-1"
    assert summary["run_status"] == "completed"
    assert summary["persisted"] is True
    assert summary["event_count"] == 2
    assert summary["tool_count"] == 1
    assert summary["tools"] == ["web_research"]
    assert summary["failed_tool_count"] == 1
    assert summary["failed_tools"] == ["web_fetch"]


def test_load_trace_readonly_reads_sqlite_without_storage_initialization(tmp_path):
    db_path = tmp_path / "sessions.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                finished_at REAL
            );
            CREATE TABLE run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE TABLE run_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                part_type TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tool_name TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE TABLE run_file_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                path TEXT NOT NULL,
                action TEXT NOT NULL,
                before_sha256 TEXT,
                after_sha256 TEXT,
                before_content TEXT,
                after_content TEXT,
                diff TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "web:smoke", "completed", '{"channel":"web"}', 1.0, 2.0, 3.0),
        )
        conn.execute(
            "INSERT INTO run_events (run_id, session_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            ("run-1", "web:smoke", TOOL_STARTED_EVENT, '{"tool_name":"web_search"}', 1.5),
        )
        conn.execute(
            "INSERT INTO run_parts (run_id, session_id, part_type, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("run-1", "web:smoke", "assistant_message", "pong", '{"ok":true}', 2.5),
        )
        conn.execute(
            """
            INSERT INTO run_file_changes (
                run_id, session_id, tool_name, path, action, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("run-1", "web:smoke", "edit_file", "a.txt", "modify", '{"ok":true}', 2.7),
        )
        conn.commit()
    finally:
        conn.close()

    trace = load_trace_readonly("web:smoke", "run-1", db_path=db_path)

    assert trace is not None
    assert trace.run.status == "completed"
    assert trace.run.metadata == {"channel": "web"}
    assert trace.events[0].payload == {"tool_name": "web_search"}
    assert trace.parts[0].content == "pong"
    assert trace.file_changes[0].path == "a.txt"


def test_check_trace_flags_web_tool_mismatch():
    no_web_case = SmokeCase("direct", "請直接回答", expect_web_tools=False)

    failures = check_trace(no_web_case, _completed_trace_summary(tools=["web_search"]))

    assert "unexpected web tool: web_search" in failures


def test_check_trace_requires_web_tool_for_web_case():
    web_case = SmokeCase("web", "請上網查", expect_web_tools=True)

    assert check_trace(web_case, _completed_trace_summary(tools=[])) == ["expected at least one web tool"]
    assert check_trace(web_case, _completed_trace_summary(tools=["web_fetch"])) == []


def test_check_trace_rejects_failed_tool_calls():
    case = SmokeCase("direct", "請直接回答", expect_web_tools=False)

    assert check_trace(
        case,
        _completed_trace_summary(
            tools=["read_file"],
            failed_tool_count=1,
            failed_tools=["read_file"],
        ),
    ) == ["1 tool call(s) failed: read_file"]


@pytest.mark.parametrize("run_status", ["", "running", "stopped", "failed"])
def test_check_trace_requires_completed_run_status(run_status):
    case = SmokeCase("direct", "answer", expect_web_tools=False)

    failures = check_trace(case, _completed_trace_summary(run_status=run_status))

    assert failures == [f"run status was {run_status or '<missing>'}; expected completed"]


def test_check_trace_requires_run_id_and_persisted_trace():
    case = SmokeCase("direct", "answer", expect_web_tools=False)
    summary = summarize_trace(None, fallback={"run_status": "completed"})

    failures = check_trace(case, summary)

    assert failures == ["missing run id", "persisted run trace was not found"]


def test_select_cases_rejects_unknown_case():
    try:
        select_cases(["missing"])
    except ValueError as exc:
        assert "Unknown smoke case(s): missing" in str(exc)
    else:
        raise AssertionError("select_cases should reject unknown ids")


def test_resolve_external_chat_prefix_uses_unique_default():
    assert resolve_external_chat_prefix(" fixed-prefix ") == "fixed-prefix"

    generated = resolve_external_chat_prefix()

    assert generated.startswith("cli-trace-smoke-")
    assert generated != "cli-trace-smoke"


def test_run_smoke_cases_uses_one_external_chat_id_for_all_cases(monkeypatch):
    seen_external_chat_ids: list[str] = []

    async def fake_send_web_chat(*args, **kwargs):
        seen_external_chat_ids.append(str(kwargs["external_chat_id"]))
        return {
            "ok": True,
            "session_id": f"web:{kwargs['external_chat_id']}",
            "run_id": f"run-{len(seen_external_chat_ids)}",
            "run_status": "completed",
            "reply": "ok",
        }

    def fake_load_trace(session_id, run_id, **kwargs):
        return StoredRunTrace(
            run=StoredRun(
                run_id=run_id,
                session_id=session_id,
                status="completed",
                created_at=1.0,
                updated_at=2.0,
            )
        )

    monkeypatch.setattr(commands.commands_chat_smoke, "load_trace_readonly", fake_load_trace)

    payload = asyncio.run(
        run_smoke_cases(
            [
                SmokeCase("one", "one", expect_web_tools=False),
                SmokeCase("two", "two", expect_web_tools=False),
            ],
            gateway_url="http://127.0.0.1:8765",
            ws_url=None,
            access_token=None,
            timeout_seconds=1,
            external_chat_prefix="smoke-session",
            db_path=None,
            send_web_chat=fake_send_web_chat,
        )
    )

    assert seen_external_chat_ids == ["smoke-session", "smoke-session"]
    assert {result["session_id"] for result in payload["results"]} == {"web:smoke-session"}
    assert payload["ok"] is True


def test_chat_smoke_command_outputs_json(monkeypatch):
    runner = CliRunner()

    async def fake_run_smoke_cases(*args, **kwargs):
        assert str(kwargs["external_chat_prefix"]).startswith("cli-trace-smoke-")
        assert kwargs["external_chat_prefix"] != "cli-trace-smoke"
        return {
            "ok": True,
            "external_chat_prefix": kwargs["external_chat_prefix"],
            "case_count": 1,
            "failed_count": 0,
            "elapsed_seconds": 0.1,
            "results": [
                {
                    "case": "pong",
                    "ok": True,
                    "prompt": "ping",
                    "session_id": "web:smoke",
                    "external_chat_id": "smoke",
                    "reply_preview": "pong",
                    "elapsed_seconds": 0.1,
                    "failures": [],
                    "trace": {"run_id": "run-1", "run_status": "completed", "tools": []},
                }
            ],
        }

    monkeypatch.setattr(commands.commands_chat_smoke, "run_smoke_cases", fake_run_smoke_cases)

    result = runner.invoke(commands.app, ["chat-smoke", "--case", "pong", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["results"][0]["trace"]["run_status"] == "completed"


def test_trace_payload_can_include_full_serialized_trace():
    trace = StoredRunTrace(
        run=StoredRun(
            run_id="run-1",
            session_id="web:smoke",
            status="completed",
            created_at=1.0,
            updated_at=2.0,
            metadata={"objective": "keep", "task_contract": {"task_type": "legacy"}},
        ),
        events=[
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type=TOOL_STARTED_EVENT,
                payload={"tool_name": "web_search"},
            ),
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type="completion_gate.evaluated",
                payload={"status": "complete"},
            ),
        ],
        parts=[
            StoredRunPart(
                run_id="run-1",
                session_id="web:smoke",
                part_type="assistant_message",
                content="pong",
                metadata={"response_len": 4, "auto_continue_attempts": 1},
            ),
            StoredRunPart(
                run_id="run-1",
                session_id="web:smoke",
                part_type="task_scorecard",
                content="legacy",
            ),
        ],
    )

    payload = trace_payload(trace, full=True)

    assert payload["ok"] is True
    assert payload["run"]["run_id"] == "run-1"
    assert payload["run"]["metadata"] == {"objective": "keep"}
    assert payload["trace"]["tools"] == ["web_search"]
    assert payload["trace"]["event_count"] == 1
    assert payload["trace"]["part_count"] == 1
    assert len(payload["events"]) == 1
    assert payload["events"][0]["event_type"] == TOOL_STARTED_EVENT
    assert len(payload["parts"]) == 1
    assert payload["parts"][0]["content"] == "pong"
    assert payload["parts"][0]["metadata"] == {"response_len": 4}


def test_run_smoke_cases_keeps_failed_payload_failed_when_trace_completed():
    async def fake_send_web_chat(*args, **kwargs):
        return {
            "ok": False,
            "error": "websocket reply timed out",
            "session_id": "web:smoke-session",
            "run_id": "",
            "run_status": "completed",
            "reply": "",
        }

    payload = asyncio.run(
        run_smoke_cases(
            [SmokeCase("one", "one", expect_web_tools=False)],
            gateway_url="http://127.0.0.1:8765",
            ws_url=None,
            access_token=None,
            timeout_seconds=1,
            external_chat_prefix="smoke-session",
            db_path=None,
            send_web_chat=fake_send_web_chat,
        )
    )

    assert payload["ok"] is False
    assert payload["failed_count"] == 1
    assert payload["results"][0]["payload_ok"] is False
    assert payload["results"][0]["failures"] == [
        "missing run id",
        "persisted run trace was not found",
        "websocket reply timed out",
    ]


def test_trace_command_outputs_json_from_readonly_db(tmp_path):
    db_path = tmp_path / "sessions.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                finished_at REAL
            );
            CREATE TABLE run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE TABLE run_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                part_type TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tool_name TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE TABLE run_file_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                path TEXT NOT NULL,
                action TEXT NOT NULL,
                before_sha256 TEXT,
                after_sha256 TEXT,
                before_content TEXT,
                after_content TEXT,
                diff TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "web:smoke", "completed", "{}", 1.0, 2.0, 3.0),
        )
        conn.execute(
            "INSERT INTO run_events (run_id, session_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            ("run-1", "web:smoke", TOOL_STARTED_EVENT, '{"tool_name":"web_search"}', 1.5),
        )
        conn.commit()
    finally:
        conn.close()

    runner = CliRunner()
    result = runner.invoke(
        commands.app,
        ["trace", "run-1", "--session-id", "web:smoke", "--db-path", str(db_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["run"]["status"] == "completed"
    assert payload["trace"]["tools"] == ["web_search"]
