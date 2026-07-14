import asyncio

import opensprite.agent.response_finalizer as response_finalizer_module
import pytest
from opensprite.agent.response_finalizer import AgentResponseFinalizer
from opensprite.config.schema import LogConfig
from opensprite.runs.trace import RunTraceRecorder


class _RunTrace:
    async def record_assistant_message_part(self, *args, **kwargs):
        pass

    async def complete_run(self, *args, **kwargs):
        pass

    async def finish_run(self, *args, **kwargs):
        pass


async def _save_assistant_message(*args, **kwargs):
    pass


def _preview(text, *, max_chars=200):
    return text[:max_chars]


def _make_finalizer(*, log_reasoning_details=False):
    return AgentResponseFinalizer(
        run_trace=_RunTrace(),
        save_assistant_message=_save_assistant_message,
        format_log_preview=_preview,
        log_config=LogConfig(log_reasoning_details=log_reasoning_details),
    )


def test_reasoning_logging_writes_summary_without_full_details(monkeypatch):
    messages = []
    monkeypatch.setattr(response_finalizer_module.logger, "info", lambda *args: messages.append(args))

    asyncio.run(
        _make_finalizer().finalize(
            session_id="session-1",
            run_id="run-1",
            response="answer",
            channel="web",
            external_chat_id=None,
            assistant_metadata={},
            run_part_metadata={},
            run_event_payload={},
            persisted_assistant_metadata={
                "llm_reasoning_details": [
                    {"type": "reasoning.text", "text": "first thought"},
                    {"type": "reasoning.text", "summary": "short"},
                ]
            },
        )
    )

    rendered = [str(item) for message in messages for item in message]
    assert any("LLM reasoning summary" in item for item in rendered)
    assert any(2 in message for message in messages)
    assert not any("first thought" in item for item in rendered)


def test_reasoning_logging_can_write_full_details(monkeypatch):
    messages = []
    monkeypatch.setattr(response_finalizer_module.logger, "info", lambda *args: messages.append(args))

    asyncio.run(
        _make_finalizer(log_reasoning_details=True).finalize(
            session_id="session-1",
            run_id="run-1",
            response="answer",
            channel="web",
            external_chat_id=None,
            assistant_metadata={},
            run_part_metadata={},
            run_event_payload={},
            persisted_assistant_metadata={
                "llm_reasoning_details": [{"type": "reasoning.text", "text": "debug thought"}]
            },
        )
    )

    rendered = [str(item) for message in messages for item in message]
    assert any("LLM reasoning details" in item for item in rendered)
    assert any("debug thought" in item for item in rendered)


def test_finalize_saves_assistant_message_with_persisted_metadata():
    saved = []

    async def save_assistant_message(session_id, content, metadata=None):
        saved.append((session_id, content, metadata))

    asyncio.run(
        AgentResponseFinalizer(
            run_trace=_RunTrace(),
            save_assistant_message=save_assistant_message,
            format_log_preview=_preview,
            log_config=LogConfig(),
        ).finalize(
            session_id="session-1",
            run_id="run-1",
            response="answer",
            channel="web",
            external_chat_id=None,
            assistant_metadata={"visible": True},
            persisted_assistant_metadata={"stored": True},
            run_part_metadata={},
            run_event_payload={},
        )
    )

    assert saved == [("session-1", "answer", {"stored": True})]


def test_finalize_visible_failure_marks_run_failed_instead_of_completed():
    calls = []

    class RecordingRunTrace:
        async def record_assistant_message_part(self, *args, **kwargs):
            calls.append(("part", args, kwargs))

        async def complete_run(self, *args, **kwargs):
            calls.append(("completed", args, kwargs))

        async def fail_run(self, *args, **kwargs):
            calls.append(("failed", args, kwargs))

    result = asyncio.run(
        AgentResponseFinalizer(
            run_trace=RecordingRunTrace(),
            save_assistant_message=_save_assistant_message,
            format_log_preview=_preview,
            log_config=LogConfig(),
        ).finalize(
            session_id="session-1",
            run_id="run-1",
            response="upload failed",
            channel="web",
            external_chat_id=None,
            assistant_metadata={},
            run_part_metadata={"reason": "media_persistence_failed"},
            run_event_payload={"reason": "media_persistence_failed"},
            terminal_status="failed",
        )
    )

    assert result.text == "upload failed"
    assert [call[0] for call in calls] == ["part", "failed"]
    assert calls[-1][2]["status"] == "failed"
    assert calls[-1][2]["event_payload"] == {
        "reason": "media_persistence_failed",
        "status": "failed",
    }


def test_finalize_stopped_run_persists_stopped_terminal_status():
    calls = []

    class RecordingRunTrace:
        async def record_assistant_message_part(self, *args, **kwargs):
            calls.append(("part", args, kwargs))

        async def complete_run(self, *args, **kwargs):
            calls.append(("completed", args, kwargs))

        async def finish_run(self, *args, **kwargs):
            calls.append(("finished", args, kwargs))

        async def fail_run(self, *args, **kwargs):
            calls.append(("failed", args, kwargs))

    asyncio.run(
        AgentResponseFinalizer(
            run_trace=RecordingRunTrace(),
            save_assistant_message=_save_assistant_message,
            format_log_preview=_preview,
        ).finalize(
            session_id="session-1",
            run_id="run-1",
            response="iteration limit reached",
            channel="web",
            external_chat_id=None,
            assistant_metadata={},
            run_part_metadata={"stop_reason": "max_tool_iterations"},
            run_event_payload={"stop_reason": "max_tool_iterations"},
            terminal_status="stopped",
        )
    )

    assert [call[0] for call in calls] == ["part", "finished"]
    assert calls[-1][2]["status"] == "stopped"


def test_run_status_persistence_failure_propagates():
    class FailingStorage:
        async def create_run(self, *args, **kwargs):
            return object()

        async def update_run_status(self, *args, **kwargs):
            raise OSError("database unavailable")

    recorder = RunTraceRecorder(storage=FailingStorage(), message_bus_getter=lambda: None)

    with pytest.raises(OSError, match="database unavailable"):
        asyncio.run(recorder.update_run_status("session-1", "run-1", "completed"))
