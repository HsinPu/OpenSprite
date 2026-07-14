from __future__ import annotations

import asyncio
import base64
import json

import pytest

from opensprite.agent.agent import AgentLoop
from opensprite.agent.execution import ExecutionResult
from opensprite.bus.message import CLIENT_TURN_ID_METADATA_KEY, UserMessage
from opensprite.config import AgentMessagesConfig, MessagesConfig
from opensprite.context.file_builder import FileContextBuilder
from opensprite.context.paths import get_session_workspace, sync_templates
from opensprite.llms.base import LLMResponse, ToolCall
from opensprite.runs.schema import (
    is_retired_lifecycle_event,
    is_retired_lifecycle_part,
    sanitize_run_metadata,
)
from opensprite.runs.trace import RunBusyError
from opensprite.storage import MemoryStorage
from opensprite.tools.registry import ToolRegistry

from agent_test_helpers import DummyTool, SavedMessageStorage, make_agent_loop, make_tool_registry


class DirectProvider:
    def __init__(self, responses: list[LLMResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self.calls.append({"messages": list(messages), "tools": list(tools or [])})
        return self.responses.pop(0)

    def get_default_model(self) -> str:
        return "fake-model"


class WorkflowDirectProvider:
    MAIN_REQUEST = "Run the implementation workflow for this change."

    def __init__(self):
        self.calls: list[dict] = []
        self.main_calls = 0

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self.calls.append({"messages": list(messages), "tools": list(tools or [])})
        latest_user_text = next(
            str(message.content)
            for message in reversed(messages)
            if getattr(message, "role", None) == "user"
        )
        if "Review the current workspace changes" in latest_user_text:
            structured_review = {
                "schema_version": 1,
                "contract": "readonly_subagent_result",
                "prompt_type": "code-reviewer",
                "status": "ok",
                "summary": "No major findings.",
                "sections": [],
                "questions": [],
                "residual_risks": [],
                "sources": [],
            }
            return LLMResponse(
                content="Review Findings\n- No major findings.\n\n```json\n"
                + json.dumps(structured_review)
                + "\n```",
                model="fake-model",
            )
        if latest_user_text == self.MAIN_REQUEST:
            self.main_calls += 1
            if self.main_calls == 1:
                return LLMResponse(
                    content="",
                    model="fake-model",
                    tool_calls=[
                        ToolCall(
                            id="workflow-call-1",
                            name="run_workflow",
                            arguments={
                                "workflow": "implement_then_review",
                                "task": "Implement a safe direct-flow integration change.",
                            },
                        )
                    ],
                )
            return LLMResponse(content="Workflow completed and merged.", model="fake-model")
        return LLMResponse(content="Implemented the requested change.", model="fake-model")

    def get_default_model(self) -> str:
        return "fake-model"


def _message(text: str = "hello") -> UserMessage:
    return UserMessage(
        text=text,
        channel="test",
        external_chat_id="room-1",
        session_id="test:room-1",
        sender_id="user-1",
        sender_name="tester",
    )


async def _close_agent(agent: AgentLoop) -> None:
    await agent.close_background_maintenance()
    await agent.close_background_processes()


def test_agent_process_calls_main_llm_directly_once(tmp_path):
    async def scenario():
        provider = DirectProvider([LLMResponse(content="assistant reply", model="fake-model")])
        storage = SavedMessageStorage()
        agent = make_agent_loop(tmp_path, provider=provider, storage=storage)
        try:
            response = await agent.process(_message())
            return response, provider, storage
        finally:
            await _close_agent(agent)

    response, provider, storage = asyncio.run(scenario())

    assert response.text == "assistant reply"
    assert len(provider.calls) == 1
    assert [entry[1] for entry in storage.saved] == ["user", "assistant"]


def test_task_shaped_request_uses_direct_turn_without_retired_lifecycle(tmp_path):
    async def scenario():
        app_home = tmp_path / "opensprite-home"
        tool_workspace = tmp_path / "workspace"
        sync_templates(app_home, silent=True)
        context_builder = FileContextBuilder(app_home=app_home, tool_workspace=tool_workspace)
        provider = DirectProvider([LLMResponse(content="implemented and verified", model="fake-model")])
        storage = MemoryStorage()
        agent = make_agent_loop(
            tmp_path,
            provider=provider,
            storage=storage,
            context_builder=context_builder,
            app_home=app_home,
            tool_workspace=tool_workspace,
        )
        session_workspace = get_session_workspace("test:room-1", workspace_root=tool_workspace)
        active_task_file = session_workspace / "ACTIVE_TASK.md"
        assert not active_task_file.exists()
        try:
            response = await agent.process(
                _message("Fix the failing tests, verify the result, and continue until the work is complete.")
            )
            run = (await storage.get_runs("test:room-1"))[0]
            events = await storage.get_run_events("test:room-1", run.run_id)
            parts = await storage.get_run_parts("test:room-1", run.run_id)
            tool_names = set(agent.tools.tool_names)
            return response, provider, run, events, parts, tool_names, active_task_file
        finally:
            await _close_agent(agent)

    response, provider, run, events, parts, tool_names, active_task_file = asyncio.run(scenario())

    assert response.text == "implemented and verified"
    assert len(provider.calls) == 1
    assert run.status == "completed"
    assert sanitize_run_metadata(run.metadata) == run.metadata
    assert not any(is_retired_lifecycle_event(event) for event in events)
    assert not any(is_retired_lifecycle_part(part) for part in parts)
    assert "task_update" not in tool_names
    assert not active_task_file.exists()
    prompt_text = "\n".join(
        str(getattr(message, "content", ""))
        for call in provider.calls
        for message in call["messages"]
    )
    assert "task_update" not in prompt_text
    assert "ACTIVE_TASK.md" not in prompt_text


def test_agent_process_propagates_client_turn_id_to_run_events_and_response(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(
            tmp_path,
            provider=DirectProvider([LLMResponse(content="assistant reply", model="fake-model")]),
            storage=storage,
        )
        message = _message("correlated")
        message.metadata[CLIENT_TURN_ID_METADATA_KEY] = "turn-current"
        try:
            response = await agent.process(message)
            run = (await storage.get_runs("test:room-1"))[0]
            events = await storage.get_run_events("test:room-1", run.run_id)
            return response, run, events
        finally:
            await _close_agent(agent)

    response, run, events = asyncio.run(scenario())

    assert response.metadata[CLIENT_TURN_ID_METADATA_KEY] == "turn-current"
    assert run.metadata[CLIENT_TURN_ID_METADATA_KEY] == "turn-current"
    assert events[0].event_type == "run_started"
    assert events[0].payload[CLIENT_TURN_ID_METADATA_KEY] == "turn-current"
    assert events[-1].event_type == "run_finished"
    assert events[-1].payload[CLIENT_TURN_ID_METADATA_KEY] == "turn-current"


def test_agent_process_uses_registered_tools_without_task_contract(tmp_path):
    async def scenario():
        tool = DummyTool(name="demo_tool", echo_value=True)
        provider = DirectProvider(
            [
                LLMResponse(
                    content="",
                    model="fake-model",
                    tool_calls=[ToolCall(id="tc1", name="demo_tool", arguments={"value": "abc"})],
                ),
                LLMResponse(content="tool finished", model="fake-model"),
            ]
        )
        storage = SavedMessageStorage()
        agent = make_agent_loop(
            tmp_path,
            provider=provider,
            storage=storage,
            tools=make_tool_registry(tool),
        )
        try:
            response = await agent.process(_message("use the demo tool"))
            return response, provider, storage
        finally:
            await _close_agent(agent)

    response, provider, storage = asyncio.run(scenario())

    assert response.text == "tool finished"
    assert len(provider.calls) == 2
    assert any(entry[1] == "tool" and entry[2] == "tool:abc" for entry in storage.saved)
    assert all(call["tools"] for call in provider.calls)


def test_agent_process_merges_registered_workflow_runtime_updates(tmp_path):
    async def scenario():
        provider = WorkflowDirectProvider()
        storage = MemoryStorage()
        agent = make_agent_loop(
            tmp_path,
            provider=provider,
            storage=storage,
            tools=ToolRegistry(),
            app_home=tmp_path / "opensprite-home",
        )
        try:
            assert "run_workflow" in agent.tools.tool_names
            response = await agent.process(_message(WorkflowDirectProvider.MAIN_REQUEST))
            runs = await storage.get_runs("test:room-1")
            parts = await storage.get_run_parts("test:room-1", runs[0].run_id)
            events = await storage.get_run_events("test:room-1", runs[0].run_id)
            response_part = next(
                part
                for part in parts
                if part.part_type == "assistant_message" and part.content == response.text
            )
            return response, provider, runs[0], response_part, events
        finally:
            await _close_agent(agent)

    response, provider, run, response_part, events = asyncio.run(scenario())

    assert response.text == "Workflow completed and merged."
    assert provider.main_calls == 2
    assert run.status == "completed"

    delegated_tasks = response_part.metadata["delegated_tasks"]
    assert {task["prompt_type"] for task in delegated_tasks} == {"implementer", "code-reviewer"}
    assert {task["status"] for task in delegated_tasks} == {"completed"}
    assert all(task["child_session_id"] for task in delegated_tasks)
    assert all(task["last_child_run_id"] for task in delegated_tasks)

    workflow_outcomes = response_part.metadata["workflow_outcomes"]
    assert len(workflow_outcomes) == 1
    assert workflow_outcomes[0]["workflow"] == "implement_then_review"
    assert workflow_outcomes[0]["status"] == "completed"
    assert workflow_outcomes[0]["total_steps"] == 2
    assert workflow_outcomes[0]["completed_steps"] == 2
    assert workflow_outcomes[0]["review_attempted"] is True
    assert workflow_outcomes[0]["review_passed"] is True
    assert "workflow.completed" in [event.event_type for event in events]


def test_cli_via_web_uses_raw_message_for_history_deduplication(tmp_path):
    async def scenario():
        provider = DirectProvider([LLMResponse(content="assistant reply", model="fake-model")])
        storage = SavedMessageStorage()
        agent = make_agent_loop(tmp_path, provider=provider, storage=storage)
        try:
            response = await agent.process(
                UserMessage(
                    text="inspect the workspace",
                    channel="web",
                    external_chat_id="browser-1",
                    session_id="web:browser-1",
                    metadata={
                        "source": "cli_via_web",
                        "gateway_url": "http://127.0.0.1:8765",
                    },
                )
            )
            return response, provider, storage, agent._context_builder.last_history
        finally:
            await _close_agent(agent)

    response, provider, storage, prompt_history = asyncio.run(scenario())

    assert response.text == "assistant reply"
    assert storage.saved[0][2] == "inspect the workspace"
    assert prompt_history == []
    prompt = provider.calls[0]["messages"][-1].content
    assert prompt.count("inspect the workspace") == 1
    assert "[Runtime context]" in prompt


def test_media_only_turn_fails_when_no_attachment_was_persisted(tmp_path):
    async def scenario():
        provider = DirectProvider([])
        storage = MemoryStorage()
        agent = make_agent_loop(
            tmp_path,
            provider=provider,
            storage=storage,
            messages_config=MessagesConfig(
                agent=AgentMessagesConfig(media_persistence_failed="custom media failure")
            ),
        )
        try:
            response = await agent.process(
                UserMessage(
                    text="",
                    channel="web",
                    external_chat_id="browser-1",
                    session_id="web:browser-1",
                    images=["not-a-data-url"],
                )
            )
            runs = await storage.get_runs("web:browser-1")
            messages = await storage.get_messages("web:browser-1")
            events = await storage.get_run_events("web:browser-1", runs[0].run_id)
            parts = await storage.get_run_parts("web:browser-1", runs[0].run_id)
            return response, provider, runs, messages, events, parts
        finally:
            await _close_agent(agent)

    response, provider, runs, messages, events, parts = asyncio.run(scenario())

    assert provider.calls == []
    assert response.text == "custom media failure"
    assert runs[0].status == "failed"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "[Media-only message could not be saved]"
    assert messages[1].content == response.text
    assert events[-1].event_type == "run_failed"
    assert events[-1].payload["reason"] == "media_persistence_failed"
    assert parts[-1].metadata["reason"] == "media_persistence_failed"


@pytest.mark.parametrize("failure_kind", ["cancelled", "error"])
def test_failed_direct_turn_clears_per_run_skill_reads(tmp_path, failure_kind):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def fail_execute(*args, **kwargs):
            entered.set()
            await release.wait()
            if failure_kind == "cancelled":
                raise asyncio.CancelledError()
            raise RuntimeError("provider failed")

        agent._execute_messages = fail_execute
        task = asyncio.create_task(agent.process(_message("use the pytest skill")))
        try:
            await entered.wait()
            active = agent.get_active_run("test:room-1")
            assert active is not None
            agent._run_skill_reads[active.run_id] = {"pytest-helper"}
            release.set()

            expected_error = asyncio.CancelledError if failure_kind == "cancelled" else RuntimeError
            with pytest.raises(expected_error):
                await task

            entries = agent.learning_ledger.recent_entries("test:room-1", limit=1)
            return active.run_id, dict(agent._run_skill_reads), entries
        finally:
            if not task.done():
                task.cancel()
            await _close_agent(agent)

    run_id, run_skill_reads, entries = asyncio.run(scenario())

    assert run_id not in run_skill_reads
    assert entries[0]["target_id"] == "pytest-helper"
    assert entries[0]["last_outcome"] == "failed"


def test_stopped_direct_turn_is_not_persisted_as_completed(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)

        async def stop_execution(*args, **kwargs):
            return ExecutionResult(
                content="I could not finish within the tool iteration limit.",
                stop_reason="max_tool_iterations",
            )

        agent._execute_messages = stop_execution
        try:
            response = await agent.process(_message("finish the task"))
            run = (await storage.get_runs("test:room-1"))[0]
            events = await storage.get_run_events("test:room-1", run.run_id)
            return response, run, events
        finally:
            await _close_agent(agent)

    response, run, events = asyncio.run(scenario())

    assert "could not finish" in response.text
    assert run.status == "stopped"
    assert events[-1].event_type == "run_finished"
    assert events[-1].payload["status"] == "stopped"


def test_cancellation_after_terminal_commit_does_not_overwrite_completed_run(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        provider = DirectProvider([LLMResponse(content="assistant reply", model="fake-model")])
        agent = make_agent_loop(tmp_path, provider=provider, storage=storage)
        entered = asyncio.Event()
        blocker = asyncio.Event()
        original_emit = agent.run_trace.emit_event

        async def blocking_terminal_emit(session_id, run_id, event_type, *args, **kwargs):
            if event_type == "run_finished":
                entered.set()
                await blocker.wait()
            return await original_emit(session_id, run_id, event_type, *args, **kwargs)

        agent.run_trace.emit_event = blocking_terminal_emit
        task = asyncio.create_task(agent.process(_message("finish once")))
        try:
            await entered.wait()
            task.cancel()
            blocker.set()
            response = await task
            run = (await storage.get_runs("test:room-1"))[0]
            messages = await storage.get_messages("test:room-1")
            events = await storage.get_run_events("test:room-1", run.run_id)
            return response, run, messages, events, task.cancelled()
        finally:
            if not task.done():
                task.cancel()
            await _close_agent(agent)

    response, run, messages, events, was_cancelled = asyncio.run(scenario())

    assert response.text == "assistant reply"
    assert run.status == "completed"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert any(event.event_type == "run_finished" for event in events)
    assert was_cancelled is False


def test_terminal_event_delivery_failure_does_not_overwrite_completed_run(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        provider = DirectProvider([LLMResponse(content="assistant reply", model="fake-model")])
        agent = make_agent_loop(tmp_path, provider=provider, storage=storage)
        original_emit = agent.run_trace.emit_event

        async def failing_terminal_emit(session_id, run_id, event_type, *args, **kwargs):
            if event_type == "run_finished":
                raise RuntimeError("live event transport failed")
            return await original_emit(session_id, run_id, event_type, *args, **kwargs)

        agent.run_trace.emit_event = failing_terminal_emit
        try:
            response = await agent.process(_message("finish despite event failure"))
            run = (await storage.get_runs("test:room-1"))[0]
            return response, run
        finally:
            await _close_agent(agent)

    response, run = asyncio.run(scenario())

    assert response.text == "assistant reply"
    assert run.status == "completed"


def test_llm_not_configured_turn_is_failed_not_completed(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(
            tmp_path,
            provider=DirectProvider([]),
            storage=storage,
            llm_configured=False,
        )
        try:
            response = await agent.process(_message("hello"))
            run = (await storage.get_runs("test:room-1"))[0]
            events = await storage.get_run_events("test:room-1", run.run_id)
            return response, run, events
        finally:
            await _close_agent(agent)

    response, run, events = asyncio.run(scenario())

    assert response.text
    assert run.status == "failed"
    assert events[-1].event_type == "run_failed"
    assert events[-1].payload["reason"] == "llm_not_configured"


def test_cancelling_during_run_start_releases_session_reservation(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)
        entered = asyncio.Event()
        blocker = asyncio.Event()
        original_emit = agent.run_trace.emit_event

        async def blocking_start_emit(session_id, run_id, event_type, *args, **kwargs):
            if event_type == "run_started":
                entered.set()
                await blocker.wait()
            return await original_emit(session_id, run_id, event_type, *args, **kwargs)

        agent.run_trace.emit_event = blocking_start_emit
        message = _message("start then cancel")
        message.metadata[CLIENT_TURN_ID_METADATA_KEY] = "turn-start-cancel"
        task = asyncio.create_task(agent.process(message))
        try:
            await entered.wait()
            assert agent.get_active_run("test:room-1") is not None
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            runs = await storage.get_runs("test:room-1")
            events = await storage.get_run_events("test:room-1", runs[0].run_id)
            messages = await storage.get_messages("test:room-1")
            return agent.get_active_run("test:room-1"), runs, events, messages
        finally:
            if not task.done():
                task.cancel()
            await _close_agent(agent)

    active, runs, events, messages = asyncio.run(scenario())

    assert active is None
    assert len(runs) == 1
    assert runs[0].status == "cancelled"
    assert runs[0].finished_at is not None
    assert events[-1].event_type == "run_cancelled"
    assert events[-1].payload[CLIENT_TURN_ID_METADATA_KEY] == "turn-start-cancel"
    assert [(message.role, message.content) for message in messages] == [
        ("user", "start then cancel")
    ]


def test_run_start_event_failure_persists_and_emits_failed_terminal(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)
        original_emit = agent.run_trace.emit_event

        async def failing_start_emit(session_id, run_id, event_type, *args, **kwargs):
            if event_type == "run_started":
                raise RuntimeError("run_started transport failed")
            return await original_emit(session_id, run_id, event_type, *args, **kwargs)

        agent.run_trace.emit_event = failing_start_emit
        message = _message("start then fail")
        message.metadata[CLIENT_TURN_ID_METADATA_KEY] = "turn-start-fail"
        try:
            with pytest.raises(RuntimeError, match="run_started transport failed"):
                await agent.process(message)
            run = (await storage.get_runs("test:room-1"))[0]
            events = await storage.get_run_events("test:room-1", run.run_id)
            return agent.get_active_run("test:room-1"), run, events
        finally:
            await _close_agent(agent)

    active, run, events = asyncio.run(scenario())

    assert active is None
    assert run.status == "failed"
    assert run.finished_at is not None
    assert events[-1].event_type == "run_failed"
    assert events[-1].payload[CLIENT_TURN_ID_METADATA_KEY] == "turn-start-fail"


def test_run_create_failure_releases_session_and_keeps_user_input(tmp_path):
    class FailingCreateStorage(MemoryStorage):
        async def create_run(self, *args, **kwargs):
            raise RuntimeError("run storage unavailable")

    async def scenario():
        storage = FailingCreateStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)
        try:
            with pytest.raises(RuntimeError, match="run storage unavailable"):
                await agent.process(_message("keep failed start"))
            messages = await storage.get_messages("test:room-1")
            return agent.get_active_run("test:room-1"), messages
        finally:
            await _close_agent(agent)

    active, messages = asyncio.run(scenario())

    assert active is None
    assert [(message.role, message.content) for message in messages] == [
        ("user", "keep failed start")
    ]


def test_media_only_partial_persistence_is_reported_as_failed(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(
            tmp_path,
            provider=DirectProvider([]),
            storage=storage,
            messages_config=MessagesConfig(
                agent=AgentMessagesConfig(
                    media_persistence_partial_failure="custom partial media failure"
                )
            ),
        )
        valid_image = "data:image/png;base64," + base64.b64encode(b"valid-image-bytes").decode("ascii")
        try:
            response = await agent.process(
                UserMessage(
                    text="",
                    channel="web",
                    external_chat_id="browser-1",
                    session_id="web:browser-1",
                    images=[valid_image, "not-a-data-url"],
                )
            )
            run = (await storage.get_runs("web:browser-1"))[0]
            messages = await storage.get_messages("web:browser-1")
            return response, run, messages
        finally:
            await _close_agent(agent)

    response, run, messages = asyncio.run(scenario())

    assert response.text == "custom partial media failure"
    assert run.status == "failed"
    assert "[Media-only message saved to workspace]" in messages[0].content
    assert "[Some media attachments could not be saved]" in messages[0].content
    assert "Unsaved attachments: 1" in messages[0].content


def test_busy_preflight_happens_before_media_persistence(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def blocking_execution(*args, **kwargs):
            entered.set()
            await release.wait()
            return ExecutionResult(content="done")

        agent._execute_messages = blocking_execution
        first = asyncio.create_task(agent.process(_message("first turn")))
        try:
            await entered.wait()

            def unexpected_persistence(*args, **kwargs):
                raise AssertionError("busy turn persisted media before rejection")

            agent.media_service.persist_inbound_media_with_events = unexpected_persistence
            with pytest.raises(RunBusyError):
                await agent.process(
                    UserMessage(
                        text="second turn",
                        channel="test",
                        external_chat_id="room-1",
                        session_id="test:room-1",
                        images=["not-a-data-url"],
                    )
                )
            release.set()
            await first
        finally:
            release.set()
            if not first.done():
                first.cancel()
            await _close_agent(agent)

    asyncio.run(scenario())


def test_mcp_connect_cancellation_keeps_original_user_message(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)
        entered = asyncio.Event()
        blocker = asyncio.Event()

        async def blocking_connect():
            entered.set()
            await blocker.wait()

        agent.connect_mcp = blocking_connect
        task = asyncio.create_task(agent.process(_message("keep this request")))
        try:
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            messages = await storage.get_messages("test:room-1")
            run = (await storage.get_runs("test:room-1"))[0]
            return messages, run
        finally:
            if not task.done():
                task.cancel()
            await _close_agent(agent)

    messages, run = asyncio.run(scenario())

    assert [(message.role, message.content) for message in messages] == [
        ("user", "keep this request")
    ]
    assert run.status == "cancelled"


def test_audio_transcription_cancellation_keeps_original_media_input(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=DirectProvider([]), storage=storage)
        entered = asyncio.Event()
        blocker = asyncio.Event()

        async def blocking_transcription(_audio_files):
            entered.set()
            await blocker.wait()
            return "unused transcript"

        agent.turn_runner.audio_input._transcribe_audio = blocking_transcription
        audio = "data:audio/wav;base64," + base64.b64encode(b"audio-bytes").decode("ascii")
        task = asyncio.create_task(
            agent.process(
                UserMessage(
                    text="",
                    channel="test",
                    external_chat_id="room-1",
                    session_id="test:room-1",
                    audios=[audio],
                    metadata={"audio_input_mode": "dictation"},
                )
            )
        )
        try:
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            messages = await storage.get_messages("test:room-1")
            run = (await storage.get_runs("test:room-1"))[0]
            return messages, run
        finally:
            if not task.done():
                task.cancel()
            await _close_agent(agent)

    messages, run = asyncio.run(scenario())

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content.startswith("[Media-only message saved to workspace]\nAudios: ")
    assert run.status == "cancelled"
