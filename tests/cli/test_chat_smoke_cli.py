import json

from typer.testing import CliRunner

from opensprite.cli import commands
from opensprite.cli.commands_chat_smoke import SmokeCase, check_trace, select_cases, summarize_trace
from opensprite.storage.base import StoredRun, StoredRunEvent, StoredRunTrace


def test_summarize_trace_extracts_profile_tools_and_completion():
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
                event_type="harness_profile.selected",
                payload={"name": "research"},
            ),
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type="task_contract.created",
                payload={"task_type": "web_research"},
            ),
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type="tool_started",
                payload={"tool_name": "web_research"},
            ),
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type="tool_result",
                payload={"tool_name": "web_fetch", "ok": False},
            ),
            StoredRunEvent(
                run_id="run-1",
                session_id="web:smoke",
                event_type="completion_gate.evaluated",
                payload={"status": "complete", "reason": "done"},
            ),
        ],
    )

    summary = summarize_trace(trace)

    assert summary["run_id"] == "run-1"
    assert summary["run_status"] == "completed"
    assert summary["profile"] == "research"
    assert summary["contract"] == "web_research"
    assert summary["tools"] == ["web_research"]
    assert summary["failed_tools"] == ["web_fetch"]
    assert summary["completion_status"] == "complete"
    assert summary["completion_reason"] == "done"


def test_check_trace_flags_removed_tool_and_web_tool_mismatch():
    no_web_case = SmokeCase("direct", "請直接回答", expect_web_tools=False)

    failures = check_trace(no_web_case, {"tools": ["search_knowledge", "web_search"]})

    assert "removed tool appeared: search_knowledge" in failures
    assert "unexpected web tool: web_search" in failures


def test_check_trace_requires_web_tool_for_web_case():
    web_case = SmokeCase("web", "請上網查", expect_web_tools=True)

    assert check_trace(web_case, {"tools": []}) == ["expected at least one web tool"]
    assert check_trace(web_case, {"tools": ["web_fetch"]}) == []


def test_select_cases_rejects_unknown_case():
    try:
        select_cases(["missing"])
    except ValueError as exc:
        assert "Unknown smoke case(s): missing" in str(exc)
    else:
        raise AssertionError("select_cases should reject unknown ids")


def test_chat_smoke_command_outputs_json(monkeypatch):
    runner = CliRunner()

    async def fake_run_smoke_cases(*args, **kwargs):
        return {
            "ok": True,
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
                    "trace": {"run_id": "run-1", "profile": "chat", "tools": []},
                }
            ],
        }

    monkeypatch.setattr(commands.commands_chat_smoke, "run_smoke_cases", fake_run_smoke_cases)

    result = runner.invoke(commands.app, ["chat-smoke", "--case", "pong", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["results"][0]["trace"]["profile"] == "chat"
