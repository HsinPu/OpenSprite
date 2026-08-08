import asyncio

import pytest

from opensprite.core.contracts.execution_events import LlmStepEvent
from opensprite.app.messaging import MessageBus
from opensprite.core.contracts.run_events import TOOL_RESULT_EVENT
from opensprite.core.contracts.run_lifecycle import (
    RUN_CANCELLED_EVENT,
    RUN_CANCELLED_STATUS,
)
from opensprite.modules.runs.presentation import serialize_run_part
from opensprite.modules.runs.trace_recorder import (
    RUN_PART_CONTENT_MAX_CHARS,
    RunEventPersistenceError,
    RunEventSink,
    RunTraceRecorder,
    truncate_run_part_content,
)
from opensprite.integrations.persistence.memory import MemoryStorage


def test_run_status_persistence_failure_propagates():
    class FailingStorage:
        async def create_run(self, *args, **kwargs):
            return object()

        async def update_run_status(self, *args, **kwargs):
            raise OSError("database unavailable")

    recorder = RunTraceRecorder(storage=FailingStorage(), message_bus_getter=lambda: None)

    with pytest.raises(OSError, match="database unavailable"):
        asyncio.run(recorder.update_run_status("session-1", "run-1", "completed"))


def test_run_trace_recorder_rejects_missing_durable_create_result():
    class MissingCreateStorage(MemoryStorage):
        async def create_run(self, *args, **kwargs):
            return None

    async def scenario():
        recorder = RunTraceRecorder(storage=MissingCreateStorage(), message_bus_getter=lambda: None)
        with pytest.raises(RuntimeError, match="did not create"):
            await recorder.create_run("web:browser-1", "run-missing")

    asyncio.run(scenario())


def test_run_trace_recorder_rejects_missing_durable_update_result():
    class MissingUpdateStorage(MemoryStorage):
        async def update_run_status(self, *args, **kwargs):
            return None

    async def scenario():
        storage = MissingUpdateStorage()
        recorder = RunTraceRecorder(storage=storage, message_bus_getter=lambda: None)
        await storage.create_run("web:browser-1", "run-1")
        with pytest.raises(RuntimeError, match="did not update"):
            await recorder.update_run_status("web:browser-1", "run-1", "completed")

    asyncio.run(scenario())


def test_run_trace_recorder_does_not_emit_completed_when_durable_update_is_missing():
    class MissingUpdateStorage(MemoryStorage):
        async def update_run_status(self, *args, **kwargs):
            return None

    async def scenario():
        storage = MissingUpdateStorage()
        bus = MessageBus()
        recorder = RunTraceRecorder(storage=storage, message_bus_getter=lambda: bus)
        await storage.create_run("web:browser-1", "run-1")
        with pytest.raises(RuntimeError, match="did not update"):
            await recorder.complete_run(
                "web:browser-1",
                "run-1",
                event_payload={"status": "completed"},
                channel="web",
                external_chat_id="browser-1",
            )
        return await storage.get_run("web:browser-1", "run-1"), bus.run_events_size

    run, live_event_count = asyncio.run(scenario())

    assert run is not None
    assert run.status == "running"
    assert live_event_count == 0


def test_cancelled_run_commit_survives_repeated_caller_cancellation():
    class BlockingCancelStorage(MemoryStorage):
        def __init__(self):
            super().__init__()
            self.cancel_update_started = asyncio.Event()
            self.release_cancel_update = asyncio.Event()

        async def update_run_status(self, session_id, run_id, status, **kwargs):
            if status == RUN_CANCELLED_STATUS:
                self.cancel_update_started.set()
                await self.release_cancel_update.wait()
            return await super().update_run_status(session_id, run_id, status, **kwargs)

    async def scenario():
        storage = BlockingCancelStorage()
        recorder = RunTraceRecorder(storage=storage, message_bus_getter=lambda: None)
        await storage.create_run("web:browser-1", "run-cancelled")
        commit = asyncio.create_task(
            recorder.fail_run(
                "web:browser-1",
                "run-cancelled",
                status=RUN_CANCELLED_STATUS,
                event_payload={"reason": "cancelled"},
            )
        )
        await storage.cancel_update_started.wait()
        commit.cancel()
        await asyncio.sleep(0)
        storage.release_cancel_update.set()
        await commit
        run = await storage.get_run("web:browser-1", "run-cancelled")
        events = await storage.get_run_events("web:browser-1", "run-cancelled")
        return run, events, commit.cancelled()

    run, events, was_cancelled = asyncio.run(scenario())

    assert run is not None
    assert run.status == RUN_CANCELLED_STATUS
    assert run.finished_at is not None
    assert events[-1].event_type == RUN_CANCELLED_EVENT
    assert was_cancelled is False


def test_truncate_run_part_content_bounds_large_payloads():
    long_content = "a" * (RUN_PART_CONTENT_MAX_CHARS + 1000) + "THE-END"

    content, metadata = truncate_run_part_content(long_content)

    assert len(content) <= RUN_PART_CONTENT_MAX_CHARS
    assert "run part content truncated" in content
    assert content.endswith("THE-END")
    assert metadata["content_truncated"] is True
    assert metadata["content_original_len"] == RUN_PART_CONTENT_MAX_CHARS + 1007


def test_run_trace_recorder_persists_bounded_parts():
    async def scenario():
        storage = MemoryStorage()
        recorder = RunTraceRecorder(storage=storage, message_bus_getter=lambda: None)
        await storage.create_run("web:browser-1", "run-1")
        await recorder.add_part(
            "web:browser-1",
            "run-1",
            "tool_result",
            content="a" * (RUN_PART_CONTENT_MAX_CHARS + 1000) + "THE-END",
            tool_name="dummy",
        )
        return await storage.get_run_parts("web:browser-1", "run-1")

    parts = asyncio.run(scenario())

    assert len(parts) == 1
    assert len(parts[0].content) <= RUN_PART_CONTENT_MAX_CHARS
    assert parts[0].content.endswith("THE-END")
    assert parts[0].metadata["content_truncated"] is True


def test_run_trace_recorder_persists_operation_audit_part():
    async def scenario():
        storage = MemoryStorage()
        recorder = RunTraceRecorder(storage=storage, message_bus_getter=lambda: None)
        await storage.create_run("web:browser-1", "run-1")
        await recorder.record_operation_audit_part(
            "web:browser-1",
            "run-1",
            {
                "operation_id": "op-1",
                "operation_type": "settings.providers.update",
                "target": "llm.providers",
                "rollback_available": True,
            },
        )
        return await storage.get_run_parts("web:browser-1", "run-1")

    parts = asyncio.run(scenario())

    assert len(parts) == 1
    assert parts[0].part_type == "operation_audit"
    assert "settings.providers.update" in parts[0].content
    assert parts[0].metadata["rollback_available"] is True


def test_run_trace_recorder_persists_llm_step_part():
    async def scenario():
        storage = MemoryStorage()
        recorder = RunTraceRecorder(storage=storage, message_bus_getter=lambda: None)
        await storage.create_run("web:browser-1", "run-1")
        await recorder.record_llm_step_parts(
            "web:browser-1",
            "run-1",
            [
                LlmStepEvent(
                    iteration=1,
                    attempt=1,
                    status="completed",
                    provider="FakeProvider",
                    model="fake-model",
                    duration_ms=12,
                    estimated_input_tokens=42,
                    message_tokens=40,
                    tool_schema_tokens=2,
                    output_tokens=7,
                    total_tokens=49,
                    finish_reason="stop",
                )
            ],
        )
        return await storage.get_run_parts("web:browser-1", "run-1")

    parts = asyncio.run(scenario())

    assert len(parts) == 1
    assert parts[0].part_type == "llm_step"
    assert "provider=FakeProvider" in parts[0].content
    assert parts[0].metadata["provider"] == "FakeProvider"
    assert parts[0].metadata["model"] == "fake-model"
    assert parts[0].metadata["estimated_input_tokens"] == 42
    assert serialize_run_part(parts[0])["artifact"]["kind"] == "llm"


def test_run_event_sink_persists_and_publishes_safe_payloads():
    async def scenario():
        storage = MemoryStorage()
        bus = MessageBus()
        sink = RunEventSink(storage=storage, message_bus_getter=lambda: bus)
        await storage.create_run("web:browser-1", "run-1")
        await sink.emit(
            "web:browser-1",
            "run-1",
            TOOL_RESULT_EVENT,
            {"tool_name": "demo", "value": object()},
            channel="web",
            external_chat_id="browser-1",
        )
        return (
            await storage.get_run_events("web:browser-1", "run-1"),
            await bus.consume_run_event(),
        )

    stored_events, bus_event = asyncio.run(scenario())

    assert len(stored_events) == 1
    assert stored_events[0].event_type == TOOL_RESULT_EVENT
    assert stored_events[0].payload["tool_name"] == "demo"
    assert isinstance(stored_events[0].payload["value"], str)
    assert bus_event.event_type == TOOL_RESULT_EVENT
    assert bus_event.payload == stored_events[0].payload
    assert bus_event.channel == "web"
    assert bus_event.external_chat_id == "browser-1"


def test_run_event_sink_can_require_durable_persistence():
    class FailingEventStorage(MemoryStorage):
        async def add_run_event(self, *args, **kwargs):
            raise OSError("storage unavailable")

    async def scenario():
        sink = RunEventSink(storage=FailingEventStorage(), message_bus_getter=lambda: MessageBus())
        await sink.emit(
            "web:browser-1",
            "run-1",
            TOOL_RESULT_EVENT,
            {"tool_name": "demo"},
            channel="web",
            external_chat_id="browser-1",
            require_persistence=True,
        )

    with pytest.raises(RunEventPersistenceError, match="Failed to persist run event"):
        asyncio.run(scenario())


def test_run_event_sink_rejects_unavailable_required_persistence():
    class UnsupportedEventStorage(MemoryStorage):
        async def add_run_event(self, *args, **kwargs):
            return None

    async def scenario():
        sink = RunEventSink(storage=UnsupportedEventStorage(), message_bus_getter=lambda: None)
        await sink.emit(
            "web:browser-1",
            "run-1",
            TOOL_RESULT_EVENT,
            {"tool_name": "demo"},
            require_persistence=True,
        )

    with pytest.raises(RunEventPersistenceError, match="persistence is unavailable"):
        asyncio.run(scenario())
