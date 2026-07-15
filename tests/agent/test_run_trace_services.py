import asyncio
from types import SimpleNamespace

import pytest

from opensprite.runs.trace import RunHookService
from opensprite.agent.execution_support.events import LlmStepEvent
from opensprite.runs.trace import (
    RUN_PART_CONTENT_MAX_CHARS,
    RunEventPersistenceError,
    RunEventSink,
    RunTraceRecorder,
    truncate_run_part_content,
)
from opensprite.bus import MessageBus
from opensprite.runs.events import (
    FILE_CHANGED_EVENT,
    RUN_PART_DELTA_EVENT,
    TOOL_RESULT_EVENT,
    TOOL_STARTED_EVENT,
    VERIFICATION_RESULT_EVENT,
    WORKFLOW_FAILED_EVENT,
)
from opensprite.runs.lifecycle import (
    RUN_CANCELLED_EVENT,
    RUN_CANCELLED_STATUS,
    RUN_COMPLETED_STATUS,
    RUN_FAILED_EVENT,
    RUN_FINISHED_EVENT,
    RUN_RUNNING_STATUS,
    RUN_STARTED_EVENT,
    RUN_STOPPED_STATUS,
)
from opensprite.runs.schema import (
    RUN_SUMMARY_STATUS_PASSED,
    RUN_WARNING_EXTERNAL_HTTP_VIA_EXEC,
    RUN_WARNING_PARALLEL_DELEGATION_FAILED,
    compact_run_events,
    serialize_file_change,
    serialize_run_artifacts,
    serialize_run_event,
    serialize_run_event_counts,
    serialize_run_events,
    serialize_run_part,
    serialize_run_parts,
    serialize_run_summary,
)
from opensprite.storage import MemoryStorage, StorageProvider


def test_run_trace_lifecycle_markers_are_stable():
    assert RUN_RUNNING_STATUS == "running"
    assert RUN_COMPLETED_STATUS == "completed"
    assert RUN_CANCELLED_STATUS == "cancelled"
    assert RUN_STARTED_EVENT == "run_started"
    assert RUN_FINISHED_EVENT == "run_finished"
    assert RUN_FAILED_EVENT == "run_failed"
    assert RUN_CANCELLED_EVENT == "run_cancelled"


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


def test_run_trace_recorder_accepts_legacy_storage_without_optional_run_api():
    class LegacyStorage(StorageProvider):
        def __init__(self):
            self.messages = {}
            self.consolidated = {}

        async def get_messages(self, session_id, limit=None):
            messages = list(self.messages.get(session_id, []))
            return messages[-limit:] if limit else messages

        async def add_message(self, session_id, message):
            self.messages.setdefault(session_id, []).append(message)

        async def clear_messages(self, session_id):
            self.messages.pop(session_id, None)

        async def get_consolidated_index(self, session_id):
            return self.consolidated.get(session_id, 0)

        async def set_consolidated_index(self, session_id, index):
            self.consolidated[session_id] = index

        async def get_all_sessions(self):
            return sorted(self.messages)

    async def scenario():
        storage = LegacyStorage()
        recorder = RunTraceRecorder(storage=storage, message_bus_getter=lambda: None)
        await recorder.create_run("web:browser-1", "run-legacy")
        await recorder.update_run_status("web:browser-1", "run-legacy", "completed")
        return await storage.get_run("web:browser-1", "run-legacy")

    assert asyncio.run(scenario()) is None


def test_run_trace_recorder_rejects_partial_optional_run_contract():
    class PartialRunStorage(StorageProvider):
        async def get_messages(self, session_id, limit=None):
            return []

        async def add_message(self, session_id, message):
            return None

        async def clear_messages(self, session_id):
            return None

        async def get_consolidated_index(self, session_id):
            return 0

        async def set_consolidated_index(self, session_id, index):
            return None

        async def get_all_sessions(self):
            return []

        async def create_run(self, *args, **kwargs):
            return SimpleNamespace(run_id="run-partial")

    async def scenario():
        recorder = RunTraceRecorder(storage=PartialRunStorage(), message_bus_getter=lambda: None)
        with pytest.raises(RuntimeError, match="implement create_run and update_run_status together"):
            await recorder.create_run("web:browser-1", "run-partial")
        with pytest.raises(RuntimeError, match="implement create_run and update_run_status together"):
            await recorder.update_run_status("web:browser-1", "run-partial", "completed")

    asyncio.run(scenario())


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


def test_serialize_run_event_builds_stable_envelope():
    event = SimpleNamespace(
        event_id=42,
        run_id="run-1",
        session_id="web:browser-1",
        event_type=TOOL_RESULT_EVENT,
        payload={"tool_name": "demo", "tool_call_id": "call-1", "ok": False, "result_preview": "failed"},
        created_at=12.5,
    )

    payload = serialize_run_event(event)

    assert payload == {
        "schema_version": 1,
        "event_id": 42,
        "run_id": "run-1",
        "session_id": "web:browser-1",
        "event_type": "tool_result",
        "kind": "tool",
        "status": "error",
        "payload": {"tool_name": "demo", "tool_call_id": "call-1", "ok": False, "result_preview": "failed"},
        "artifact": {
            "schema_version": 1,
            "artifact_id": "tool:call-1",
            "artifact_type": "tool",
            "kind": "tool",
            "status": "error",
            "phase": "result",
            "tool_name": "demo",
            "tool_call_id": "call-1",
            "iteration": None,
            "title": "demo",
            "detail": "failed",
        },
        "created_at": 12.5,
    }


def test_serialize_run_event_projects_tool_trace_metadata():
    event = SimpleNamespace(
        event_id=45,
        run_id="run-1",
        session_id="web:browser-1",
        event_type=TOOL_RESULT_EVENT,
        payload={
            "tool_name": "web_search",
            "tool_call_id": "call-1",
            "ok": False,
            "result_preview": "{\"type\":\"web_search\",\"provider\":\"searxng\"}",
            "type": "web_search",
            "query": "Qwen latest model 2026",
            "provider": "searxng",
            "backend": "searxng",
            "search_provider": "searxng",
            "search_backend": "searxng",
            "returned_items": 0,
            "error": "403 Forbidden",
        },
        created_at=13.0,
    )

    payload = serialize_run_event(event)

    assert payload["artifact"]["metadata"] == {
        "type": "web_search",
        "query": "Qwen latest model 2026",
        "provider": "searxng",
        "backend": "searxng",
        "search_provider": "searxng",
        "search_backend": "searxng",
        "returned_items": 0,
        "error": "403 Forbidden",
    }


def test_serialize_run_event_projects_curator_artifact():
    event = SimpleNamespace(
        event_id=45,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="curator.completed",
        payload={
            "status": "completed",
            "changed": ["memory", "skills"],
            "summary": "Updated memory and skills.",
        },
        created_at=13.0,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "completed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "curator",
        "artifact_type": "curator",
        "kind": "work",
        "status": "completed",
        "title": "Curator",
        "detail": "Updated memory and skills.",
        "metadata": {
            "status": "completed",
            "changed": ["memory", "skills"],
            "summary": "Updated memory and skills.",
        },
    }


def test_serialize_run_event_projects_curator_job_artifact():
    event = SimpleNamespace(
        event_id=46,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="curator.job.completed",
        payload={
            "status": "completed",
            "job": "memory",
            "label": "memory",
            "summary": "Updated memory.",
        },
        created_at=13.0,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "completed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "curator_job:memory",
        "artifact_type": "curator_job",
        "kind": "work",
        "status": "completed",
        "title": "Curator job: memory",
        "detail": "Updated memory.",
        "metadata": {
            "status": "completed",
            "job": "memory",
            "label": "memory",
            "summary": "Updated memory.",
        },
    }


def test_serialize_run_event_projects_curator_job_failed_artifact():
    event = SimpleNamespace(
        event_id=47,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="curator.job.failed",
        payload={
            "status": "failed",
            "job": "memory",
            "label": "memory",
            "error": "memory broke",
            "error_type": "RuntimeError",
        },
        created_at=13.0,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "failed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "curator_job:memory",
        "artifact_type": "curator_job",
        "kind": "work",
        "status": "failed",
        "title": "Curator job: memory",
        "detail": "memory broke",
        "metadata": {
            "status": "failed",
            "job": "memory",
            "label": "memory",
            "error": "memory broke",
            "error_type": "RuntimeError",
        },
    }


def test_serialize_run_event_projects_curator_failed_artifact():
    event = SimpleNamespace(
        event_id=47,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="curator.failed",
        payload={
            "status": "failed",
            "error": "memory broke",
            "job": "memory",
        },
        created_at=13.0,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "failed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "curator",
        "artifact_type": "curator",
        "kind": "work",
        "status": "failed",
        "title": "Curator",
        "detail": "memory broke",
        "metadata": {
            "status": "failed",
            "error": "memory broke",
            "job": "memory",
        },
    }


def test_serialize_run_event_projects_subagent_artifact():
    event = SimpleNamespace(
        event_id=48,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="subagent.completed",
        payload={
            "status": "completed",
            "task_id": "task_abc12345",
            "prompt_type": "implementer",
            "child_session_id": "web:browser-1:subagent:task_abc12345",
            "child_run_id": "run_child_1",
            "parent_session_id": "web:browser-1",
            "parent_run_id": "run-1",
            "resume": False,
            "summary": "Applied focused implementation changes.",
        },
        created_at=13.25,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "completed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "subagent:task_abc12345",
        "artifact_type": "subagent_task",
        "kind": "work",
        "status": "completed",
        "title": "Subagent: implementer",
        "detail": "Applied focused implementation changes.",
        "metadata": {
            "status": "completed",
            "task_id": "task_abc12345",
            "prompt_type": "implementer",
            "child_session_id": "web:browser-1:subagent:task_abc12345",
            "child_run_id": "run_child_1",
            "parent_session_id": "web:browser-1",
            "parent_run_id": "run-1",
            "resume": False,
            "summary": "Applied focused implementation changes.",
        },
    }


def test_serialize_run_event_projects_cancelled_subagent_artifact():
    event = SimpleNamespace(
        event_id=49,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="subagent.cancelled",
        payload={
            "status": "cancelled",
            "task_id": "task_abc12345",
            "prompt_type": "researcher",
            "child_session_id": "web:browser-1:subagent:task_abc12345",
            "child_run_id": "run_child_2",
            "parent_session_id": "web:browser-1",
            "parent_run_id": "run-1",
            "resume": False,
            "error": "cancelled",
        },
        created_at=13.5,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "cancelled"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "subagent:task_abc12345",
        "artifact_type": "subagent_task",
        "kind": "work",
        "status": "cancelled",
        "title": "Subagent: researcher",
        "detail": "cancelled",
        "metadata": {
            "status": "cancelled",
            "task_id": "task_abc12345",
            "prompt_type": "researcher",
            "child_session_id": "web:browser-1:subagent:task_abc12345",
            "child_run_id": "run_child_2",
            "parent_session_id": "web:browser-1",
            "parent_run_id": "run-1",
            "resume": False,
            "error": "cancelled",
        },
    }


def test_serialize_run_event_projects_parallel_subagent_group_artifact():
    event = SimpleNamespace(
        event_id=50,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="subagent.group.completed",
        payload={
            "status": "completed",
            "group_id": "fanout_abc12345",
            "total_tasks": 2,
            "max_parallel": 2,
            "completed_count": 2,
            "failed_count": 0,
            "cancelled_count": 0,
            "task_ids": ["task_a", "task_b"],
            "tasks": [
                {"task_id": "task_a", "prompt_type": "researcher", "status": "completed"},
                {"task_id": "task_b", "prompt_type": "code-reviewer", "status": "completed"},
            ],
            "summary": "Completed 2/2 parallel subagent task(s).",
        },
        created_at=13.75,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "completed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "subagent_group:fanout_abc12345",
        "artifact_type": "subagent_group",
        "kind": "work",
        "status": "completed",
        "title": "Parallel subagents",
        "detail": "Completed 2/2 parallel subagent task(s).",
        "metadata": {
            "status": "completed",
            "group_id": "fanout_abc12345",
            "total_tasks": 2,
            "max_parallel": 2,
            "completed_count": 2,
            "failed_count": 0,
            "cancelled_count": 0,
            "task_ids": ["task_a", "task_b"],
            "tasks": [
                {"task_id": "task_a", "prompt_type": "researcher", "status": "completed"},
                {"task_id": "task_b", "prompt_type": "code-reviewer", "status": "completed"},
            ],
            "summary": "Completed 2/2 parallel subagent task(s).",
        },
    }


def test_serialize_run_event_projects_workflow_artifact():
    event = SimpleNamespace(
        event_id=51,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="workflow.completed",
        payload={
            "workflow_run_id": "workflow_abc12345",
            "workflow": "implement_then_review",
            "status": "completed",
            "summary": "Completed 2/2 workflow step(s).",
            "total_steps": 2,
        },
        created_at=14.0,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "completed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "workflow:workflow_abc12345",
        "artifact_type": "workflow",
        "kind": "work",
        "status": "completed",
        "title": "Workflow: implement_then_review",
        "detail": "Completed 2/2 workflow step(s).",
        "metadata": {
            "workflow_run_id": "workflow_abc12345",
            "workflow": "implement_then_review",
            "status": "completed",
            "summary": "Completed 2/2 workflow step(s).",
            "total_steps": 2,
        },
    }


def test_serialize_run_event_projects_workflow_step_artifact():
    event = SimpleNamespace(
        event_id=52,
        run_id="run-1",
        session_id="web:browser-1",
        event_type="workflow.step.completed",
        payload={
            "workflow_run_id": "workflow_abc12345",
            "workflow": "implement_then_review",
            "step_id": "review",
            "label": "Code review",
            "prompt_type": "code-reviewer",
            "step_index": 2,
            "total_steps": 2,
            "summary": "No major findings.",
            "status": "completed",
        },
        created_at=14.2,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "work"
    assert payload["status"] == "completed"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "workflow_step:workflow_abc12345:review",
        "artifact_type": "workflow_step",
        "kind": "work",
        "status": "completed",
        "title": "Workflow step: Code review",
        "detail": "No major findings.",
        "metadata": {
            "workflow_run_id": "workflow_abc12345",
            "workflow": "implement_then_review",
            "step_id": "review",
            "label": "Code review",
            "prompt_type": "code-reviewer",
            "step_index": 2,
            "total_steps": 2,
            "summary": "No major findings.",
            "status": "completed",
        },
    }


def test_serialize_run_event_classifies_part_delta_as_streaming_text():
    event = SimpleNamespace(
        event_id=44,
        run_id="run-1",
        session_id="web:browser-1",
        event_type=RUN_PART_DELTA_EVENT,
        payload={"part_id": "assistant-1", "part_type": "assistant_message", "content_delta": "hello"},
        created_at=13.0,
    )

    payload = serialize_run_event(event)

    assert payload["kind"] == "text"
    assert payload["status"] == "running"
    assert payload["artifact"] is None


def test_compact_run_events_keeps_lifecycle_events_over_text_noise():
    events = []
    for index in range(90):
        events.append(
            SimpleNamespace(
                event_id=index + 1,
                run_id="run-1",
                session_id="web:browser-1",
                event_type=TOOL_RESULT_EVENT,
                payload={"tool_name": f"tool-{index}"},
                created_at=float(index),
            )
        )
    for index in range(30):
        events.append(
            SimpleNamespace(
                event_id=1000 + index,
                run_id="run-1",
                session_id="web:browser-1",
                event_type=RUN_PART_DELTA_EVENT,
                payload={"content_delta": str(index)},
                created_at=100.0 + index,
            )
        )

    compacted = compact_run_events(events)
    payload = serialize_run_events(events)

    assert len(compacted) == 104
    assert sum(1 for event in compacted if event.event_type == RUN_PART_DELTA_EVENT) == 24
    assert sum(1 for event in compacted if event.event_type == TOOL_RESULT_EVENT) == 80
    assert compacted[0].event_id == 11
    assert compacted[-1].event_id == 1029
    assert len(payload) == 104
    assert payload[-1]["event_type"] == RUN_PART_DELTA_EVENT
    assert serialize_run_event_counts(events, payload) == {
        "total": 120,
        "returned": 104,
        "compacted": 16,
        "text_total": 30,
        "text_returned": 24,
        "max_events": 80,
        "max_text_events": 24,
    }


def test_serialize_file_changed_event_projects_the_durable_change_identity():
    event = SimpleNamespace(
        event_id=43,
        run_id="run-1",
        session_id="web:browser-1",
        event_type=FILE_CHANGED_EVENT,
        payload={
            "change_id": 3,
            "tool_name": "apply_patch",
            "path": "notes.txt",
            "action": "modify",
            "diff_len": 9,
            "diff_preview": "-old +new",
        },
        created_at=12.75,
    )

    payload = serialize_run_event(event)

    assert payload["payload"]["change_id"] == 3
    assert payload["artifact"]["artifact_id"] == "file_change:3"
    assert payload["artifact"]["source_id"] == "3"


def test_llm_delta_hook_emits_empty_completion_marker():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_llm_delta_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("assistant:run-1:1", "", "running", 1)
        await hook("assistant:run-1:1", "", "completed", 2)

    asyncio.run(scenario())

    assert len(calls) == 1
    assert calls[0][0] == "web:browser-1"
    assert calls[0][1] == "run-1"
    assert calls[0][2] == RUN_PART_DELTA_EVENT
    assert calls[0][3] == {
        "part_id": "assistant:run-1:1",
        "part_type": "assistant_message",
        "content_delta": "",
        "state": "completed",
        "sequence": 2,
    }
    assert calls[0][4] == {"channel": "web", "external_chat_id": "browser-1"}


def test_llm_status_hook_uses_structured_status_only():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_llm_status_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("The article says retry policies are useful.")
        await hook({"message": "Retrying provider request.", "status": "retry", "trigger": "provider_retry"})

    asyncio.run(scenario())

    assert calls == [
        (
            "web:browser-1",
            "run-1",
            "llm_status",
            {"message": "The article says retry policies are useful."},
            {"channel": "web", "external_chat_id": "browser-1"},
        ),
        (
            "web:browser-1",
            "run-1",
            "llm_status",
            {"status": "retry", "trigger": "provider_retry", "message": "Retrying provider request."},
            {"channel": "web", "external_chat_id": "browser-1"},
        ),
    ]


def test_tool_input_delta_hook_emits_tool_input_events():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_tool_input_delta_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("call-1", "demo", '{"value"', 1)

    asyncio.run(scenario())

    assert calls == [
        (
            "web:browser-1",
            "run-1",
            "tool_input_delta",
            {"tool_call_id": "call-1", "tool_name": "demo", "input_delta": '{"value"', "sequence": 1},
            {"channel": "web", "external_chat_id": "browser-1"},
        )
    ]


def test_reasoning_delta_hook_emits_inspector_only_events():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_reasoning_delta_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("thinking", 1)

    asyncio.run(scenario())

    assert calls == [
        (
            "web:browser-1",
            "run-1",
            "reasoning_delta",
            {"content_delta": "thinking", "sequence": 1, "inspector_only": True},
            {"channel": "web", "external_chat_id": "browser-1"},
        )
    ]


def test_serialize_run_part_builds_stable_artifact_shape():
    part = SimpleNamespace(
        part_id=7,
        run_id="run-1",
        session_id="web:browser-1",
        part_type="tool_result",
        tool_name="demo",
        content="failed",
        metadata={"tool_call_id": "call-1", "ok": False, "result_preview": "failed"},
        created_at=13.0,
    )

    payload = serialize_run_part(part)

    assert payload["schema_version"] == 1
    assert payload["part_id"] == 7
    assert payload["kind"] == "tool"
    assert payload["state"] == "error"
    assert payload["metadata"] == {"tool_call_id": "call-1", "ok": False, "result_preview": "failed"}
    assert payload["artifact"]["artifact_id"] == "tool:call-1"
    assert payload["artifact"]["phase"] == "tool_result"
    assert payload["artifact"]["status"] == "error"


def test_serialize_file_change_builds_stable_snapshot_shape():
    change = SimpleNamespace(
        change_id=3,
        run_id="run-1",
        session_id="web:browser-1",
        tool_name="apply_patch",
        path="notes.txt",
        action="modify",
        before_sha256="before",
        after_sha256="after",
        before_content="old",
        after_content="new",
        diff="-old\n+new",
        metadata={"diff_len": 9},
        created_at=14.0,
    )

    payload = serialize_file_change(change)

    assert payload["schema_version"] == 1
    assert payload["change_id"] == 3
    assert payload["kind"] == "file"
    assert payload["state"] == "completed"
    assert payload["path"] == "notes.txt"
    assert payload["before_content"] == "old"
    assert payload["after_content"] == "new"
    assert payload["artifact"] == {
        "schema_version": 1,
        "artifact_id": "file_change:3",
        "artifact_type": "file_change",
        "kind": "file",
        "status": "completed",
        "path": "notes.txt",
        "action": "modify",
        "tool_name": "apply_patch",
        "diff_len": 9,
        "snapshots_available": {"before": True, "after": True},
        "metadata": {"diff_len": 9},
    }


def test_serialize_run_artifacts_merges_tool_event_and_part_by_call_id():
    trace = SimpleNamespace(
        events=[
            SimpleNamespace(
                event_id=1,
                run_id="run-1",
                session_id="web:browser-1",
                event_type=TOOL_STARTED_EVENT,
                payload={"tool_name": "demo", "tool_call_id": "call-1", "args_preview": "{}"},
                created_at=10.0,
            ),
            SimpleNamespace(
                event_id=2,
                run_id="run-1",
                session_id="web:browser-1",
                event_type=TOOL_RESULT_EVENT,
                payload={"tool_name": "demo", "tool_call_id": "call-1", "ok": True, "result_preview": "done"},
                created_at=11.0,
            ),
        ],
        parts=[
            SimpleNamespace(
                part_id=7,
                run_id="run-1",
                session_id="web:browser-1",
                part_type="tool_result",
                tool_name="demo",
                content="done",
                metadata={"tool_call_id": "call-1", "ok": True, "result_preview": "done"},
                created_at=12.0,
            )
        ],
        file_changes=[],
    )

    artifacts = serialize_run_artifacts(trace)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact["artifact_id"] == "tool:call-1"
    assert artifact["kind"] == "tool"
    assert artifact["status"] == "completed"
    assert artifact["phase"] == "tool_result"
    assert artifact["tool_call_id"] == "call-1"
    assert artifact["source"] == "part"
    assert artifact["sources"] == ["event", "part"]


def test_serialize_run_summary_builds_stable_card_payload():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-1",
            session_id="web:browser-1",
            status="completed",
            metadata={"objective": "Ship the fix", "verification_attempted": True, "verification_passed": True},
            created_at=10.0,
            updated_at=15.0,
            finished_at=16.5,
        ),
        events=[
            SimpleNamespace(
                event_id=1,
                run_id="run-1",
                session_id="web:browser-1",
                event_type=TOOL_STARTED_EVENT,
                payload={"tool_name": "demo", "tool_call_id": "call-1"},
                created_at=11.0,
            ),
            SimpleNamespace(
                event_id=2,
                run_id="run-1",
                session_id="web:browser-1",
                event_type=VERIFICATION_RESULT_EVENT,
                payload={"ok": True, "verification_status": "passed", "verification_name": "pytest", "result_preview": "ok"},
                created_at=14.0,
            ),
            SimpleNamespace(
                event_id=3,
                run_id="run-1",
                session_id="web:browser-1",
                event_type="subagent.group.completed",
                payload={
                    "status": "completed",
                    "group_id": "fanout_abc12345",
                    "total_tasks": 2,
                    "max_parallel": 2,
                    "completed_count": 2,
                    "failed_count": 0,
                    "cancelled_count": 0,
                    "task_ids": ["task_a", "task_b"],
                    "tasks": [
                        {"task_id": "task_a", "prompt_type": "researcher", "status": "completed", "summary": "ok:a"},
                        {"task_id": "task_b", "prompt_type": "code-reviewer", "status": "completed", "summary": "ok:b"},
                    ],
                    "summary": "Completed 2/2 parallel subagent task(s).",
                },
                created_at=15.5,
            ),
        ],
        parts=[
            SimpleNamespace(
                part_id=1,
                run_id="run-1",
                session_id="web:browser-1",
                part_type="tool_call",
                tool_name="demo",
                content="{}",
                metadata={"tool_call_id": "call-1"},
                created_at=11.5,
            )
        ],
        file_changes=[
            SimpleNamespace(
                change_id=5,
                run_id="run-1",
                session_id="web:browser-1",
                tool_name="apply_patch",
                path="notes.txt",
                action="modify",
                before_sha256="before",
                after_sha256="after",
                before_content="old",
                after_content="new",
                diff="-old\n+new",
                metadata={"diff_len": 9},
                created_at=13.0,
            )
        ],
    )

    summary = serialize_run_summary(trace)

    assert summary["schema_version"] == 1
    assert summary["run_id"] == "run-1"
    assert summary["objective"] == "Ship the fix"
    assert summary["duration_seconds"] == 6.5
    assert summary["tools"] == [{"name": "demo", "count": 1}]
    assert summary["verification"] == {
        "attempted": True,
        "passed": True,
        "status": RUN_SUMMARY_STATUS_PASSED,
        "name": "pytest",
        "summary": "ok",
    }
    assert summary["structured_subagents"] == {
        "total": 0,
        "by_prompt_type": {},
        "by_status": {},
        "total_sections": 0,
        "total_items": 0,
        "total_findings": 0,
        "total_questions": 0,
        "total_residual_risks": 0,
        "results": [],
    }
    assert summary["parallel_delegation"] == {
        "group_count": 1,
        "task_count": 2,
        "groups": [
            {
                "group_id": "fanout_abc12345",
                "status": "completed",
                "total_tasks": 2,
                "max_parallel": 2,
                "completed_count": 2,
                "failed_count": 0,
                "cancelled_count": 0,
                "summary": "Completed 2/2 parallel subagent task(s).",
                "tasks": [
                    {"task_id": "task_a", "prompt_type": "researcher", "status": "completed", "summary": "ok:a"},
                    {"task_id": "task_b", "prompt_type": "code-reviewer", "status": "completed", "summary": "ok:b"},
                ],
                "created_at": 15.5,
            }
        ],
    }
    assert summary["artifact_counts"] == {"total": 4, "tool": 1, "file": 1, "verification": 1}
    assert summary["warnings"] == []
    assert summary["counts"] == {"events": 3, "parts": 1, "tool_calls": 1, "file_changes": 1}


def test_serialize_run_summary_warns_on_external_http_exec():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-http-exec",
            session_id="web:browser-1",
            status="completed",
            metadata={"objective": "Fetch market data"},
            created_at=10.0,
            updated_at=12.0,
            finished_at=12.0,
        ),
        events=[],
        parts=[
            SimpleNamespace(
                part_id=1,
                run_id="run-http-exec",
                session_id="web:browser-1",
                part_type="tool_result",
                tool_name="exec",
                content='{"stat":"OK"}',
                metadata={
                    "ok": True,
                    "tool_call_id": "call-http",
                    "external_http_via_exec": True,
                    "warning": "external HTTP fetched via exec instead of web_fetch",
                },
                created_at=11.0,
            )
        ],
        file_changes=[],
    )

    summary = serialize_run_summary(trace)

    assert RUN_WARNING_EXTERNAL_HTTP_VIA_EXEC in summary["warnings"]


def test_serialize_run_summary_warns_when_run_stopped():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-stopped",
            session_id="web:browser-1",
            status=RUN_STOPPED_STATUS,
            metadata={"objective": "Long task"},
            created_at=10.0,
            updated_at=11.0,
            finished_at=12.0,
        ),
        events=[],
        parts=[],
        file_changes=[],
    )

    summary = serialize_run_summary(trace)

    assert summary["warnings"] == [RUN_STOPPED_STATUS]


def test_serialize_run_summary_collects_structured_subagent_results():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-structured",
            session_id="web:browser-structured",
            status="completed",
            metadata={"objective": "Structured review"},
            created_at=20.0,
            updated_at=24.0,
            finished_at=25.0,
        ),
        events=[
            SimpleNamespace(
                event_id=1,
                run_id="run-structured",
                session_id="web:browser-structured",
                event_type="subagent.completed",
                payload={
                    "status": "completed",
                    "task_id": "task_review",
                    "prompt_type": "code-reviewer",
                    "summary": "One correctness risk found.",
                    "structured_output": {
                        "schema_version": 1,
                        "contract": "readonly_subagent_result",
                        "prompt_type": "code-reviewer",
                        "status": "ok",
                        "summary": "One correctness risk found.",
                        "section_count": 1,
                        "item_count": 1,
                        "finding_count": 1,
                        "question_count": 0,
                        "residual_risk_count": 1,
                        "sections": [
                            {
                                "key": "findings",
                                "title": "Review Findings",
                                "type": "finding_list",
                                "items": [{"title": "Null handling", "severity": "high"}],
                            }
                        ],
                        "questions": [],
                        "residual_risks": ["Did not run integration tests."],
                        "sources": [{"kind": "file", "path": "src/foo.py", "start_line": 10, "end_line": 14}],
                        "truncated": False,
                    },
                },
                created_at=22.0,
            ),
        ],
        parts=[],
        file_changes=[],
    )

    summary = serialize_run_summary(trace)

    assert summary["structured_subagents"] == {
        "total": 1,
        "by_prompt_type": {"code-reviewer": 1},
        "by_status": {"ok": 1},
        "total_sections": 1,
        "total_items": 1,
        "total_findings": 1,
        "total_questions": 0,
        "total_residual_risks": 1,
        "results": [
            {
                "task_id": "task_review",
                "prompt_type": "code-reviewer",
                "status": "ok",
                "summary": "One correctness risk found.",
                "section_count": 1,
                "item_count": 1,
                "finding_count": 1,
                "question_count": 0,
                "residual_risk_count": 1,
                "created_at": 22.0,
            }
        ],
    }


def test_serialize_run_summary_collects_workflow_results():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-workflow-summary",
            session_id="web:browser-workflow",
            status="completed",
            metadata={"objective": "Workflow summary"},
            created_at=30.0,
            updated_at=35.0,
            finished_at=36.0,
        ),
        events=[
            SimpleNamespace(
                event_id=1,
                run_id="run-workflow-summary",
                session_id="web:browser-workflow",
                event_type="workflow.completed",
                payload={
                    "workflow_run_id": "workflow_abc12345",
                    "workflow": "implement_then_review",
                    "status": "completed",
                    "task_preview": "Implement a safe change.",
                    "total_steps": 2,
                    "completed_steps": 2,
                    "failed_steps": 0,
                    "summary": "Completed 2/2 workflow step(s).",
                },
                created_at=34.0,
            ),
        ],
        parts=[],
        file_changes=[],
    )

    summary = serialize_run_summary(trace)

    assert summary["workflows"] == {
        "total": 1,
        "by_workflow": {"implement_then_review": 1},
        "by_status": {"completed": 1},
        "results": [
            {
                "workflow_run_id": "workflow_abc12345",
                "workflow": "implement_then_review",
                "status": "completed",
                "task_preview": "Implement a safe change.",
                "total_steps": 2,
                "completed_steps": 2,
                "failed_steps": 0,
                "summary": "Completed 2/2 workflow step(s).",
                "created_at": 34.0,
            }
        ],
    }


def test_serialize_run_summary_collects_failed_workflow_follow_up_detail():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-workflow-failed",
            session_id="web:browser-workflow",
            status="completed",
            metadata={"objective": "Workflow summary"},
            created_at=30.0,
            updated_at=35.0,
            finished_at=36.0,
        ),
        events=[
            SimpleNamespace(
                event_id=1,
                run_id="run-workflow-failed",
                session_id="web:browser-workflow",
                event_type=WORKFLOW_FAILED_EVENT,
                payload={
                    "workflow_run_id": "workflow_abc12345",
                    "workflow": "implement_then_review",
                    "status": "failed",
                    "task_preview": "Implement a safe change.",
                    "total_steps": 2,
                    "completed_steps": 1,
                    "failed_steps": 1,
                    "summary": "Workflow stopped after 1/2 completed step(s).",
                    "next_step_id": "review",
                    "next_step_label": "Code review",
                    "error": "review step failed",
                },
                created_at=34.0,
            ),
        ],
        parts=[],
        file_changes=[],
    )

    summary = serialize_run_summary(trace)

    assert summary["workflows"] == {
        "total": 1,
        "by_workflow": {"implement_then_review": 1},
        "by_status": {"failed": 1},
        "results": [
            {
                "workflow_run_id": "workflow_abc12345",
                "workflow": "implement_then_review",
                "status": "failed",
                "task_preview": "Implement a safe change.",
                "total_steps": 2,
                "completed_steps": 1,
                "failed_steps": 1,
                "summary": "Resolve the Code review step failure: review step failed",
                "created_at": 34.0,
            }
        ],
    }


def test_serialize_run_summary_marks_parallel_delegation_warnings():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-2",
            session_id="web:browser-2",
            status="completed",
            metadata={"objective": "Review in parallel"},
            created_at=10.0,
            updated_at=12.0,
            finished_at=13.0,
        ),
        events=[
            SimpleNamespace(
                event_id=1,
                run_id="run-2",
                session_id="web:browser-2",
                event_type="subagent.group.failed",
                payload={
                    "status": "failed",
                    "group_id": "fanout_warn",
                    "total_tasks": 2,
                    "max_parallel": 2,
                    "completed_count": 1,
                    "failed_count": 1,
                    "cancelled_count": 0,
                    "task_ids": ["task_a", "task_b"],
                    "tasks": [
                        {"task_id": "task_a", "prompt_type": "researcher", "status": "completed"},
                        {"task_id": "task_b", "prompt_type": "code-reviewer", "status": "failed", "error": "broken"},
                    ],
                    "summary": "Completed 1/2 parallel subagent task(s); 1 failed.",
                },
                created_at=12.5,
            ),
        ],
        parts=[],
        file_changes=[],
    )

    summary = serialize_run_summary(trace)

    assert summary["parallel_delegation"]["group_count"] == 1
    assert summary["warnings"] == [RUN_WARNING_PARALLEL_DELEGATION_FAILED]


def test_serialize_run_summary_includes_structured_subagents():
    trace = SimpleNamespace(
        run=SimpleNamespace(
            run_id="run-3",
            session_id="web:browser-3",
            status="completed",
            metadata={"objective": "Review with structure"},
            created_at=20.0,
            updated_at=24.0,
            finished_at=25.0,
        ),
        events=[
            SimpleNamespace(
                event_id=1,
                run_id="run-3",
                session_id="web:browser-3",
                event_type="subagent.completed",
                payload={
                    "status": "completed",
                    "task_id": "task_review",
                    "prompt_type": "code-reviewer",
                    "summary": "One correctness risk found.",
                    "structured_output": {
                        "schema_version": 1,
                        "contract": "readonly_subagent_result",
                        "prompt_type": "code-reviewer",
                        "status": "ok",
                        "summary": "One correctness risk found.",
                        "section_count": 1,
                        "item_count": 1,
                        "finding_count": 1,
                        "question_count": 0,
                        "residual_risk_count": 1,
                        "sections": [
                            {
                                "key": "findings",
                                "title": "Review Findings",
                                "type": "finding_list",
                                "items": [{"title": "Null handling", "severity": "high"}],
                            }
                        ],
                        "questions": [],
                        "residual_risks": ["Did not run integration tests."],
                        "sources": [{"kind": "file", "path": "src/foo.py", "start_line": 10, "end_line": 14}],
                        "truncated": False,
                    },
                },
                created_at=22.0,
            ),
        ],
        parts=[],
        file_changes=[],
    )

    summary = serialize_run_summary(trace)

    assert summary["structured_subagents"] == {
        "total": 1,
        "by_prompt_type": {"code-reviewer": 1},
        "by_status": {"ok": 1},
        "total_sections": 1,
        "total_items": 1,
        "total_findings": 1,
        "total_questions": 0,
        "total_residual_risks": 1,
        "results": [
            {
                "task_id": "task_review",
                "prompt_type": "code-reviewer",
                "status": "ok",
                "summary": "One correctness risk found.",
                "section_count": 1,
                "item_count": 1,
                "finding_count": 1,
                "question_count": 0,
                "residual_risk_count": 1,
                "created_at": 22.0,
            }
        ],
    }
