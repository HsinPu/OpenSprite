import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from opensprite.agent.agent import AgentLoop
from opensprite.agent import media_runtime
from opensprite.agent.execution import ExecutionResult
from opensprite.agent.execution_support.events import ContextCompactionEvent
from opensprite.runs.trace import RunBusyError
from opensprite.runs.events import VERIFICATION_NAME_METADATA_FIELD, VERIFICATION_STATUS_METADATA_FIELD
from opensprite.agent.turn_result_updates import apply_runtime_file_changes, merge_workflow_outcomes
from opensprite.bus import MessageBus
from opensprite.bus.events import InboundMessage, OutboundMessage
from opensprite.config.schema import AgentConfig, Config, HistorySearchConfig, LogConfig, MemoryConfig, MessagesConfig, RecentSummaryConfig, ToolsConfig, UserProfileConfig
from opensprite.context.paths import get_session_skills_dir
from opensprite.bus.message import UserMessage
from opensprite.llms.base import LLMResponse, ToolCall
from opensprite.runs.events import (
    CURATOR_STARTED_EVENT,
    FILE_CHANGED_EVENT,
    LLM_STATUS_EVENT,
    TOOL_RESULT_EVENT,
    TOOL_STARTED_EVENT,
    VERIFICATION_RESULT_EVENT,
    VERIFICATION_STARTED_EVENT,
)
from opensprite.runs.lifecycle import RUN_FINISHED_EVENT, RUN_STARTED_EVENT
from opensprite.media.router import MediaRouter
from opensprite.storage import MemoryStorage, StoredDelegatedTask
from opensprite.storage.base import StoredMessage
from opensprite.tools.base import Tool
from opensprite.tools.process_runtime import BackgroundSession
from opensprite.tools.registry import ToolRegistry
from opensprite.tools.result_status import tool_error_result
from opensprite.tools.shell_runtime import CapturedOutputChunk
from tests.agent.agent_test_helpers import make_tool_registry


class FakeContextBuilder:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.last_history = None

    def build_system_prompt(self, session_id: str = "default") -> str:
        return "system"

    def build_messages(self, history, current_message, current_images=None, channel=None, session_id=None):
        self.last_history = list(history)
        return [{"role": "user", "content": current_message}]

    def add_tool_result(self, messages, tool_call_id, tool_name, result):
        return messages

    def add_assistant_message(self, messages, content, tool_calls=None):
        return messages


def _python_shell_command(code: str) -> str:
    argv = [sys.executable, "-u", "-c", code]
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def _extract_session_id(result: str) -> str:
    for line in result.splitlines():
        if line.startswith("Session ID: "):
            return line.removeprefix("Session ID: ").strip()
    raise AssertionError(f"Session ID missing from result: {result}")


class FakeProvider:
    async def chat(self, messages, tools=None, model=None, **kwargs):
        return LLMResponse(content="assistant reply", model=model or "fake-model")

    def get_default_model(self) -> str:
        return "fake-model"














class FakeSpeechProvider:
    async def transcribe(self, audio_data_url, *, model=None, language=None):
        return "請幫我整理這段語音重點"




def test_apply_runtime_file_changes_merges_counts_and_paths():
    result = apply_runtime_file_changes(
        ExecutionResult(content="ok", file_change_count=1, touched_paths=("a.py",)),
        {"file_change_count": 3, "touched_paths": ("a.py", "b.py", " ")},
    )

    assert result.file_change_count == 3
    assert result.touched_paths == ("a.py", "b.py")




def test_merge_workflow_outcomes_normalizes_workflow_run_ids():
    merged = merge_workflow_outcomes(
        (
            {"workflow_run_id": " workflow_review ", "status": "initial"},
            {"workflow_run_id": "", "status": "ignored"},
            {"status": "missing_id"},
        ),
        (
            {"workflow_run_id": "workflow_fix", "status": "new"},
            {"workflow_run_id": " workflow_review ", "status": "updated"},
        ),
    )

    assert [item["status"] for item in merged] == ["new", "updated"]


class FakeStorage:
    def __init__(self):
        self.saved = []

    async def get_messages(self, session_id, limit=None):
        return []

    async def add_message(self, session_id, message: StoredMessage):
        self.saved.append((session_id, message.role, message.content, dict(message.metadata)))

    async def clear_messages(self, session_id):
        return None

    async def get_consolidated_index(self, session_id):
        return 0

    async def set_consolidated_index(self, session_id, index):
        return None

    async def get_all_sessions(self):
        return []


class HistoryStorage(FakeStorage):
    def __init__(self, messages):
        super().__init__()
        self.messages = list(messages)

    async def get_messages(self, session_id, limit=None):
        if limit is None:
            return list(self.messages)
        return list(self.messages[-limit:])


class FakeBus:
    def __init__(self):
        self.inbound: list[InboundMessage] = []
        self.outbound: list[OutboundMessage] = []

    async def publish_inbound(self, message: InboundMessage) -> None:
        self.inbound.append(message)

    async def publish_outbound(self, message: OutboundMessage) -> None:
        self.outbound.append(message)


class DummyTool(Tool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "dummy"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def _execute(self, **kwargs):
        return "ok"


class LargeSchemaTool(Tool):
    @property
    def name(self) -> str:
        return "large"

    @property
    def description(self) -> str:
        return "large schema tool"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "string",
                    "description": "x" * 2000,
                }
            },
        }

    async def _execute(self, **kwargs):
        return "ok"


def _image_data_url(payload: bytes, mime_type: str = "image/png") -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _media_data_url(payload: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_curator_skill_snapshot_is_session_scoped(tmp_path):
    workspace = tmp_path / "workspace"
    session_a_skills = get_session_skills_dir("web:browser-a", workspace_root=workspace)
    session_b_skills = get_session_skills_dir("web:browser-b", workspace_root=workspace)
    skill_dir = session_a_skills / "session-a-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("session a only", encoding="utf-8")
    registry = ToolRegistry()
    registry.register(DummyTool())

    agent = AgentLoop(
        config=Config.load_agent_template_config(),
        provider=FakeProvider(),
        storage=FakeStorage(),
        context_builder=FakeContextBuilder(workspace),
        tools=registry,
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        **Config.packaged_agent_llm_chat_kwargs(),
    )

    assert agent._read_skill_snapshot("web:browser-a")
    assert agent._read_skill_snapshot("web:browser-b") == ""




def test_agent_process_persists_user_then_assistant_then_runs_maintenance(tmp_path):
    async def scenario():
        registry = ToolRegistry()
        registry.register(DummyTool())
        storage = FakeStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path),
            tools=registry,
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        call_order = []
        release_maintenance = asyncio.Event()

        async def fake_call_llm(session_id, current_message, channel=None, user_images=None, allow_tools=True, **kwargs):
            call_order.append(("call_llm", session_id, current_message, channel, list(user_images or [])))
            assert storage.saved[0][1] == "user"
            return ExecutionResult(content="assistant reply", executed_tool_calls=0, used_configure_skill=False)

        async def fake_consolidate(session_id):
            await release_maintenance.wait()
            call_order.append(("memory", session_id))

        async def fake_update_profile(session_id):
            await release_maintenance.wait()
            call_order.append(("profile", session_id))

        async def fake_update_recent_summary(session_id):
            await release_maintenance.wait()
            call_order.append(("recent-summary", session_id))

        agent.call_llm = fake_call_llm
        agent._maybe_consolidate_memory = fake_consolidate
        agent._maybe_update_recent_summary = fake_update_recent_summary
        agent._maybe_update_user_profile = fake_update_profile

        response = await agent.process(
            UserMessage(
                text="hello",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
                sender_id="user-1",
                sender_name="alice",
                images=["img1"],
                metadata={"source": "test"},
            )
        )

        assert call_order == [
            ("call_llm", "telegram:room-1", "hello", "telegram", ["img1"]),
        ]

        release_maintenance.set()
        await agent.wait_for_background_maintenance()

        return response, storage, call_order

    response, storage, call_order = asyncio.run(scenario())

    assert [entry[1] for entry in storage.saved] == ["user", "assistant"]
    assert storage.saved[0][3]["sender_name"] == "alice"
    assert storage.saved[0][3]["images_count"] == 1
    assert storage.saved[1][3] == {"channel": "telegram", "external_chat_id": "room-1"}
    assert call_order[0] == ("call_llm", "telegram:room-1", "hello", "telegram", ["img1"])
    assert set(call_order[1:]) == {
        ("memory", "telegram:room-1"),
        ("recent-summary", "telegram:room-1"),
        ("profile", "telegram:room-1"),
    }
    assert response.text == "assistant reply"
    assert response.channel == "telegram"
    assert response.session_id == "telegram:room-1"


def test_agent_process_emits_run_lifecycle_events(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        async def fake_call_llm(*args, **kwargs):
            return ExecutionResult(
                content="assistant reply",
                executed_tool_calls=0,
                context_compactions=1,
                context_compaction_events=[
                    ContextCompactionEvent(
                        trigger="proactive",
                        strategy="deterministic",
                        outcome="compacted",
                        iteration=1,
                        messages_before=8,
                        messages_after=3,
                    )
                ],
            )

        agent.call_llm = fake_call_llm
        agent._schedule_curator = lambda session_id, run_id, channel, external_chat_id, result: None

        response = await agent.process(
            UserMessage(
                text="hello",
                channel="web",
                external_chat_id="browser-1",
                session_id="web:browser-1",
                sender_id="user-1",
            )
        )

        run = next(iter(storage._runs.values()))
        events = next(iter(storage._run_events.values()))
        parts = await storage.get_run_parts("web:browser-1", run.run_id)
        return response, run, events, parts

    response, run, events, parts = asyncio.run(scenario())

    assert response.text == "assistant reply"
    assert run.status == "completed"
    assert run.session_id == "web:browser-1"
    assert [event.event_type for event in events] == [
        RUN_STARTED_EVENT,
        LLM_STATUS_EVENT,
        RUN_FINISHED_EVENT,
    ]
    assert events[0].payload["status"] == "running"
    assert events[-1].payload["status"] == "completed"
    assert [part.part_type for part in parts] == ["context_compaction", "assistant_message"]
    assert parts[0].content == "proactive:deterministic:compacted"
    assert parts[0].metadata["messages_before"] == 8
    assert parts[1].content == "assistant reply"
    assert parts[1].metadata["executed_tool_calls"] == 0
    assert parts[1].metadata["context_compactions"] == 1


def test_agent_process_schedules_curator_after_run_finished(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        async def fake_call_llm(*args, **kwargs):
            return ExecutionResult(content="assistant reply", executed_tool_calls=0)

        async def fake_maintenance(session_id):
            return None

        agent.call_llm = fake_call_llm
        agent._maybe_consolidate_memory = fake_maintenance
        agent._maybe_update_recent_summary = fake_maintenance
        agent._maybe_update_user_profile = fake_maintenance

        await agent.process(
            UserMessage(
                text="hello",
                channel="web",
                external_chat_id="browser-1",
                session_id="web:browser-1",
                sender_id="user-1",
            )
        )
        await agent.wait_for_background_maintenance()

        run = next(iter(storage._runs.values()))
        return await storage.get_run_events("web:browser-1", run.run_id)

    events = asyncio.run(scenario())
    event_types = [event.event_type for event in events]

    assert RUN_FINISHED_EVENT in event_types
    assert CURATOR_STARTED_EVENT in event_types
    assert event_types.index(RUN_FINISHED_EVENT) < event_types.index(CURATOR_STARTED_EVENT)


def test_agent_verify_hooks_emit_verification_events(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        bus = MessageBus()
        agent._message_bus = bus
        await storage.create_run("web:browser-1", "run-1")

        before = agent.agent_run_hooks.make_tool_progress_hook(
            channel="web",
            external_chat_id="browser-1",
            session_id="web:browser-1",
            run_id="run-1",
            enabled=True,
        )
        after = agent.agent_run_hooks.make_tool_result_hook(
            channel="web",
            external_chat_id="browser-1",
            session_id="web:browser-1",
            run_id="run-1",
            enabled=True,
        )

        await before("verify", {"action": "python_compile", "path": "src"})
        await after("verify", {"action": "python_compile", "path": "src"}, "Verification passed: python_compile")

        stored_events = await storage.get_run_events("web:browser-1", "run-1")
        stored_parts = await storage.get_run_parts("web:browser-1", "run-1")
        bus_events = []
        while bus.run_events_size:
            bus_events.append(await bus.consume_run_event())
        return stored_events, stored_parts, bus_events

    stored_events, stored_parts, bus_events = asyncio.run(scenario())

    assert [event.event_type for event in stored_events] == [
        TOOL_STARTED_EVENT,
        VERIFICATION_STARTED_EVENT,
        TOOL_RESULT_EVENT,
        VERIFICATION_RESULT_EVENT,
    ]
    assert [event.event_type for event in bus_events] == [event.event_type for event in stored_events]
    assert stored_events[1].payload == {"action": "python_compile", "path": "src"}
    assert stored_events[-1].payload["ok"] is True
    assert stored_events[-1].payload[VERIFICATION_STATUS_METADATA_FIELD] == "passed"
    assert stored_events[-1].payload[VERIFICATION_NAME_METADATA_FIELD] == "python_compile"
    assert stored_events[0].payload["state"] == "running"
    assert stored_events[0].payload["started_at"] > 0
    assert stored_events[2].payload["state"] == "completed"
    assert stored_events[2].payload["started_at"] == stored_events[0].payload["started_at"]
    assert stored_events[2].payload["finished_at"] >= stored_events[2].payload["started_at"]
    assert stored_events[2].payload["duration_ms"] >= 0
    assert [part.part_type for part in stored_parts] == ["tool_call", "tool_result"]
    assert [part.tool_name for part in stored_parts] == ["verify", "verify"]
    assert stored_parts[0].metadata["args"] == {"action": "python_compile", "path": "src"}
    assert stored_parts[0].metadata["state"] == "running"
    assert stored_parts[0].metadata["started_at"] == stored_events[0].payload["started_at"]
    assert stored_parts[1].metadata["ok"] is True
    assert stored_parts[1].metadata["state"] == "completed"
    assert stored_parts[1].metadata["duration_ms"] >= 0
    assert stored_parts[1].content == "Verification passed: python_compile"


def test_agent_tool_result_hook_marks_error_executing_results_failed(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        await storage.create_run("web:browser-1", "run-1")
        after = agent.agent_run_hooks.make_tool_result_hook(
            channel="web",
            external_chat_id="browser-1",
            session_id="web:browser-1",
            run_id="run-1",
            enabled=True,
        )

        await after(
            "web_fetch",
            {"url": "https://example.test/missing"},
            tool_error_result(
                "HTTP Error: 404 Not Found",
                error_type="ToolExecutionError",
                metadata={"tool_name": "web_fetch"},
            ),
        )

        return await storage.get_run_events("web:browser-1", "run-1"), await storage.get_run_parts("web:browser-1", "run-1")

    stored_events, stored_parts = asyncio.run(scenario())

    assert stored_events[-1].event_type == TOOL_RESULT_EVENT
    assert stored_events[-1].payload["ok"] is False
    assert stored_events[-1].payload["state"] == "error"
    assert stored_events[-1].payload["error"] == "HTTP Error: 404 Not Found"
    assert stored_events[-1].payload["error_type"] == "ToolExecutionError"
    assert stored_events[-1].payload["status_code"] == 404
    assert stored_parts[-1].metadata["ok"] is False
    assert stored_parts[-1].metadata["state"] == "error"
    assert stored_parts[-1].metadata["error"] == "HTTP Error: 404 Not Found"
    assert stored_parts[-1].metadata["error_type"] == "ToolExecutionError"
    assert stored_parts[-1].metadata["status_code"] == 404


def test_agent_tool_result_hook_marks_structured_json_error_failed(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        await storage.create_run("web:browser-1", "run-1")
        after = agent.agent_run_hooks.make_tool_result_hook(
            channel="web",
            external_chat_id="browser-1",
            session_id="web:browser-1",
            run_id="run-1",
            enabled=True,
        )
        result = json.dumps({"type": "web_search", "ok": False, "error": "Search failed"})

        await after("web_search", {"query": "Qwen"}, result)

        return await storage.get_run_events("web:browser-1", "run-1"), await storage.get_run_parts("web:browser-1", "run-1")

    stored_events, stored_parts = asyncio.run(scenario())

    assert stored_events[-1].payload["ok"] is False
    assert stored_events[-1].payload["state"] == "error"
    assert stored_events[-1].payload["error"] == "Search failed"
    assert stored_events[-1].payload["error_type"] == "ToolError"
    assert stored_parts[-1].metadata["ok"] is False
    assert stored_parts[-1].metadata["state"] == "error"
    assert stored_parts[-1].metadata["error"] == "Search failed"


def test_agent_tool_result_hook_records_search_trace_metadata(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        await storage.create_run("web:browser-1", "run-1")
        after = agent.agent_run_hooks.make_tool_result_hook(
            channel="web",
            external_chat_id="browser-1",
            session_id="web:browser-1",
            run_id="run-1",
            enabled=True,
        )
        result = json.dumps(
            {
                "type": "web_search",
                "ok": False,
                "query": "Qwen latest model 2026",
                "provider": "searxng",
                "backend": "searxng",
                "error": "Client error '403 Forbidden'",
            }
        )

        await after("web_search", {"query": "Qwen latest model 2026"}, result)

        return await storage.get_run_events("web:browser-1", "run-1"), await storage.get_run_parts("web:browser-1", "run-1")

    stored_events, stored_parts = asyncio.run(scenario())

    payload = stored_events[-1].payload
    metadata = stored_parts[-1].metadata
    assert payload["provider"] == "searxng"
    assert payload["backend"] == "searxng"
    assert payload["query"] == "Qwen latest model 2026"
    assert payload["error"] == "Client error '403 Forbidden'"
    assert metadata["provider"] == "searxng"
    assert metadata["backend"] == "searxng"
    assert metadata["search_provider"] == "searxng"
    assert metadata["search_backend"] == "searxng"


def test_agent_default_filesystem_tools_record_run_file_changes(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        await storage.create_run("web:browser-1", "run-1")

        session_token = agent._current_session_id.set("web:browser-1")
        channel_token = agent._current_channel.set("web")
        transport_token = agent._current_external_chat_id.set("browser-1")
        run_token = agent._current_run_id.set("run-1")
        try:
            result = await agent.tools.execute(
                "write_file",
                {"path": "notes.txt", "content": "hello\n"},
            )
        finally:
            agent._current_run_id.reset(run_token)
            agent._current_external_chat_id.reset(transport_token)
            agent._current_channel.reset(channel_token)
            agent._current_session_id.reset(session_token)

        changes = await storage.get_run_file_changes("web:browser-1", "run-1")
        events = await storage.get_run_events("web:browser-1", "run-1")
        return result, changes, events

    result, changes, events = asyncio.run(scenario())

    assert "Successfully wrote to notes.txt" in result
    assert len(changes) == 1
    assert changes[0].tool_name == "write_file"
    assert changes[0].path == "notes.txt"
    assert changes[0].action == "add"
    assert changes[0].before_sha256 is None
    assert changes[0].after_sha256 == _sha256("hello\n")
    assert changes[0].before_content is None
    assert changes[0].after_content == "hello\n"
    assert "+++ b/notes.txt" in changes[0].diff
    assert changes[0].metadata["diff_len"] == len(changes[0].diff)
    assert changes[0].metadata["after_content_available"] is True
    assert [event.event_type for event in events] == [FILE_CHANGED_EVENT]
    assert events[0].payload["path"] == "notes.txt"


def test_agent_process_persists_media_only_message_without_llm(tmp_path):
    async def scenario():
        registry = ToolRegistry()
        registry.register(DummyTool())
        storage = FakeStorage()
        context_builder = FakeContextBuilder(tmp_path / "workspace")
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=context_builder,
            tools=registry,
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        async def fail_call_llm(*args, **kwargs):
            raise AssertionError("media-only messages should not call the LLM")

        async def fake_maintenance(session_id):
            return None

        agent.call_llm = fail_call_llm
        agent._maybe_consolidate_memory = fake_maintenance
        agent._maybe_update_recent_summary = fake_maintenance
        agent._maybe_update_user_profile = fake_maintenance

        response = await agent.process(
            UserMessage(
                text="",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
                images=[_image_data_url(b"image-bytes")],
                audios=[_media_data_url(b"audio-bytes", "audio/ogg")],
                videos=[_media_data_url(b"video-bytes", "video/mp4")],
            )
        )
        await agent.wait_for_background_maintenance()
        return response, storage, context_builder.workspace

    response, storage, workspace_root = asyncio.run(scenario())

    user_metadata = storage.saved[0][3]
    image_files = user_metadata["image_files"]
    audio_files = user_metadata["audio_files"]
    video_files = user_metadata["video_files"]
    saved_image = workspace_root / "sessions" / "telegram" / "room-1" / image_files[0]
    saved_audio = workspace_root / "sessions" / "telegram" / "room-1" / audio_files[0]
    saved_video = workspace_root / "sessions" / "telegram" / "room-1" / video_files[0]

    assert response.text == "已收到並保存媒體檔案。需要我分析內容時，請直接告訴我要看哪一個檔案。"
    assert user_metadata["images_dir"] == "images"
    assert user_metadata["audios_dir"] == "audios"
    assert user_metadata["videos_dir"] == "videos"
    assert image_files[0].startswith("images/inbound-")
    assert image_files[0].endswith(".png")
    assert audio_files[0].startswith("audios/inbound-")
    assert audio_files[0].endswith(".ogg")
    assert video_files[0].startswith("videos/inbound-")
    assert video_files[0].endswith(".mp4")
    assert saved_image.read_bytes() == b"image-bytes"
    assert saved_audio.read_bytes() == b"audio-bytes"
    assert saved_video.read_bytes() == b"video-bytes"
    assert [entry[1] for entry in storage.saved] == ["user", "assistant"]
    assert storage.saved[0][2].startswith("[Media-only message saved to workspace]")
    assert f"Images: {image_files[0]}" in storage.saved[0][2]
    assert f"Audios: {audio_files[0]}" in storage.saved[0][2]
    assert f"Videos: {video_files[0]}" in storage.saved[0][2]


def test_agent_process_routes_audio_only_message_to_llm(tmp_path):
    async def scenario():
        registry = ToolRegistry()
        registry.register(DummyTool())
        storage = FakeStorage()
        context_builder = FakeContextBuilder(tmp_path / "workspace")
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=context_builder,
            tools=registry,
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            media_router=MediaRouter(speech_provider=FakeSpeechProvider()),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        captured = {}

        async def fake_call_llm(
            session_id,
            current_message,
            channel=None,
            user_images=None,
            user_image_files=None,
            user_audio_files=None,
            user_video_files=None,
            allow_tools=True,
            **kwargs,
        ):
            captured.setdefault("current_message", current_message)
            captured.setdefault("current_audios", list(media_runtime.get_current_audios(agent) or []))
            captured.setdefault("user_audio_files", list(user_audio_files or []))
            return ExecutionResult(content="transcript reply", executed_tool_calls=1, used_configure_skill=False)

        async def fake_maintenance(session_id):
            return None

        agent.call_llm = fake_call_llm
        agent._maybe_consolidate_memory = fake_maintenance
        agent._maybe_update_recent_summary = fake_maintenance
        agent._maybe_update_user_profile = fake_maintenance

        response = await agent.process(
            UserMessage(
                text="",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
                audios=[_media_data_url(b"audio-bytes", "audio/ogg")],
                metadata={"audio_kinds": ["voice"]},
            )
        )
        await agent.wait_for_background_maintenance()
        return response, captured, storage

    response, captured, storage = asyncio.run(scenario())

    assert response.text == "transcript reply"
    assert captured["current_message"].startswith("請幫我整理這段語音重點")
    assert "[Uploaded file path(s): audios/inbound-" in captured["current_message"]
    assert captured["current_audios"] == []
    assert captured["user_audio_files"] == []
    assert [entry[1] for entry in storage.saved] == ["user", "assistant"]


def test_agent_process_saves_uploaded_audio_without_pretranscribing(tmp_path):
    async def scenario():
        registry = ToolRegistry()
        registry.register(DummyTool())
        storage = FakeStorage()
        context_builder = FakeContextBuilder(tmp_path / "workspace")
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=context_builder,
            tools=registry,
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            media_router=MediaRouter(speech_provider=FakeSpeechProvider()),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        async def fail_call_llm(*args, **kwargs):
            raise AssertionError("uploaded audio files without text should not call the LLM")

        async def fake_maintenance(session_id):
            return None

        agent.call_llm = fail_call_llm
        agent._maybe_consolidate_memory = fake_maintenance
        agent._maybe_update_recent_summary = fake_maintenance
        agent._maybe_update_user_profile = fake_maintenance

        response = await agent.process(
            UserMessage(
                text="",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
                audios=[_media_data_url(b"audio-bytes", "audio/mpeg")],
                metadata={"audio_kinds": ["audio"]},
            )
        )
        await agent.wait_for_background_maintenance()
        return response, storage

    response, storage = asyncio.run(scenario())

    assert response.text == "已收到並保存媒體檔案。需要我分析內容時，請直接告訴我要看哪一個檔案。"
    assert storage.saved[0][3]["audio_files"][0].startswith("audios/inbound-")
    assert storage.saved[0][3]["audio_kinds"] == ["audio"]


def test_agent_process_passes_saved_media_paths_when_text_requests_analysis(tmp_path):
    async def scenario():
        registry = ToolRegistry()
        registry.register(DummyTool())
        storage = FakeStorage()
        context_builder = FakeContextBuilder(tmp_path / "workspace")
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=context_builder,
            tools=registry,
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        captured = {}

        async def fake_call_llm(
            session_id,
            current_message,
            channel=None,
            user_images=None,
            user_image_files=None,
            user_audio_files=None,
            user_video_files=None,
            allow_tools=True,
            **kwargs,
        ):
            captured.setdefault("current_message", current_message)
            captured.setdefault("user_image_files", list(user_image_files or []))
            captured.setdefault("user_audio_files", list(user_audio_files or []))
            captured.setdefault("user_video_files", list(user_video_files or []))
            return ExecutionResult(content="analysis reply", executed_tool_calls=0, used_configure_skill=False)

        async def fake_maintenance(session_id):
            return None

        agent.call_llm = fake_call_llm
        agent._maybe_consolidate_memory = fake_maintenance
        agent._maybe_update_recent_summary = fake_maintenance
        agent._maybe_update_user_profile = fake_maintenance

        response = await agent.process(
            UserMessage(
                text="請幫我分析這些檔案",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
                images=[_image_data_url(b"image-bytes")],
                audios=[_media_data_url(b"audio-bytes", "audio/ogg")],
                videos=[_media_data_url(b"video-bytes", "video/mp4")],
            )
        )
        await agent.wait_for_background_maintenance()
        return response, captured

    response, captured = asyncio.run(scenario())

    assert response.text == "analysis reply"
    assert captured["current_message"] == "請幫我分析這些檔案"
    assert captured["user_image_files"][0].startswith("images/inbound-")
    assert captured["user_audio_files"][0].startswith("audios/inbound-")
    assert captured["user_video_files"][0].startswith("videos/inbound-")














def test_agent_process_rejects_overlapping_runs_for_same_session(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        blocker = asyncio.Event()

        async def fake_execute_messages(*args, **kwargs):
            await blocker.wait()
            return ExecutionResult(content="done", executed_tool_calls=0)

        agent._execute_messages = fake_execute_messages
        first = asyncio.create_task(
            agent.process(
                UserMessage(
                    text="Please implement the change.",
                    channel="web",
                    external_chat_id="browser-1",
                    session_id="web:browser-1",
                )
            )
        )
        for _ in range(100):
            if agent.get_active_run("web:browser-1") is not None:
                break
            await asyncio.sleep(0.001)
        else:
            raise AssertionError("active run was not registered")

        try:
            await agent.process(
                UserMessage(
                    text="Please implement another change.",
                    channel="web",
                    external_chat_id="browser-1",
                    session_id="web:browser-1",
                )
            )
        except RunBusyError:
            pass
        else:
            raise AssertionError("RunBusyError was not raised")
        blocker.set()
        await first

    asyncio.run(scenario())


def test_agent_process_cancel_request_marks_run_cancelled_and_clears_active_run(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        async def fake_execute_messages(*args, **kwargs):
            should_cancel = kwargs.get("should_cancel")
            for _ in range(200):
                if callable(should_cancel) and should_cancel():
                    raise asyncio.CancelledError()
                await asyncio.sleep(0.001)
            return ExecutionResult(content="done", executed_tool_calls=0)

        agent._execute_messages = fake_execute_messages
        task = asyncio.create_task(
            agent.process(
                UserMessage(
                    text="Please implement the change.",
                    channel="web",
                    external_chat_id="browser-1",
                    session_id="web:browser-1",
                )
            )
        )
        for _ in range(100):
            active = agent.get_active_run("web:browser-1")
            if active is not None:
                break
            await asyncio.sleep(0.001)
        else:
            raise AssertionError("active run was not registered")

        accepted = await agent.request_run_cancel(
            "web:browser-1",
            active.run_id,
            channel="web",
            external_chat_id="browser-1",
        )
        assert accepted is True

        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("process task was not cancelled")

        run = await storage.get_run("web:browser-1", active.run_id)
        events = await storage.get_run_events("web:browser-1", active.run_id)
        return run, events, agent.get_active_run("web:browser-1")

    run, events, active = asyncio.run(scenario())

    assert run is not None
    assert run.status == "cancelled"
    assert [event.event_type for event in events][-2:] == ["run_cancel_requested", "run_cancelled"]
    assert active is None


def test_agent_process_cancel_request_kills_owned_background_sessions(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        session_ids: list[str] = []

        async def fake_execute_messages(*args, **kwargs):
            exec_tool = agent.tools.get("exec")
            assert exec_tool is not None
            started = await exec_tool.execute(
                command=_python_shell_command(
                    "import time; print('owned background', flush=True); time.sleep(5)"
                ),
                background=True,
                timeout_seconds=5,
                notify_on_exit=False,
            )
            session_ids.append(_extract_session_id(started))
            should_cancel = kwargs.get("should_cancel")
            for _ in range(200):
                if callable(should_cancel) and should_cancel():
                    raise asyncio.CancelledError()
                await asyncio.sleep(0.01)
            return ExecutionResult(content="done", executed_tool_calls=1)

        agent._execute_messages = fake_execute_messages
        task = asyncio.create_task(
            agent.process(
                UserMessage(
                    text="Please implement the change.",
                    channel="web",
                    external_chat_id="browser-1",
                    session_id="web:browser-1",
                )
            )
        )
        for _ in range(100):
            active = agent.get_active_run("web:browser-1")
            if active is not None and session_ids:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("active run or background session was not registered")

        accepted = await agent.request_run_cancel(
            "web:browser-1",
            active.run_id,
            channel="web",
            external_chat_id="browser-1",
        )
        assert accepted is True

        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("process task was not cancelled")

        assert agent.background_process_manager is not None
        session = await agent.background_process_manager.get_session(session_ids[0])
        events = await storage.get_run_events("web:browser-1", active.run_id)
        return session, events

    session, events = asyncio.run(scenario())

    assert session is not None
    assert session.state == "exited"
    assert session.termination_reason == "killed"
    assert session.owner_session_id == "web:browser-1"
    assert session.owner_run_id is not None
    event_types = [event.event_type for event in events]
    assert event_types.index("run_cancel_requested") < event_types.index("run_cancelled")


def test_agent_cancel_request_retries_background_cleanup_without_duplicate_event(tmp_path):
    class FlakyBackgroundProcessManager:
        def __init__(self):
            self.calls: list[tuple[str, str | None]] = []

        async def kill_owned_sessions(self, session_id, *, run_id=None):
            self.calls.append((session_id, run_id))
            if len(self.calls) == 1:
                raise RuntimeError("background cleanup interrupted")
            return []

    async def scenario():
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=MemoryStorage(),
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(
                **{**Config.load_template_data()["user_profile"], "enabled": False}
            ),
            recent_summary_config=RecentSummaryConfig(
                **{**Config.load_template_data()["recent_summary"], "enabled": False}
            ),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        manager = FlakyBackgroundProcessManager()
        agent.background_process_manager = manager
        emitted_events: list[str] = []

        async def record_event(_session_id, _run_id, event_type, _payload, **_kwargs):
            emitted_events.append(event_type)

        agent._emit_run_event = record_event
        agent.run_state.start("web:browser-1", "run-1")

        accepted = await agent.request_run_cancel("web:browser-1", "run-1")
        return accepted, manager.calls, emitted_events

    accepted, calls, emitted_events = asyncio.run(scenario())

    assert accepted is True
    assert calls == [
        ("web:browser-1", "run-1"),
        ("web:browser-1", "run-1"),
    ]
    assert emitted_events == ["run_cancel_requested"]


def test_agent_cancel_request_finishes_background_cleanup_when_caller_is_cancelled(tmp_path):
    class BlockingBackgroundProcessManager:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.completed = False

        async def kill_owned_sessions(self, _session_id, *, run_id=None):
            assert run_id == "run-1"
            self.started.set()
            await self.release.wait()
            self.completed = True
            return []

    async def scenario():
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=MemoryStorage(),
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(
                **{**Config.load_template_data()["user_profile"], "enabled": False}
            ),
            recent_summary_config=RecentSummaryConfig(
                **{**Config.load_template_data()["recent_summary"], "enabled": False}
            ),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        manager = BlockingBackgroundProcessManager()
        agent.background_process_manager = manager
        agent.run_state.start("web:browser-1", "run-1")

        request = asyncio.create_task(agent.request_run_cancel("web:browser-1", "run-1"))
        await manager.started.wait()
        request.cancel()
        manager.release.set()
        try:
            await request
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancel request did not preserve caller cancellation")
        return manager.completed

    assert asyncio.run(scenario()) is True


def test_agent_cancel_request_starts_background_cleanup_before_event_failure(tmp_path):
    class RecordingBackgroundProcessManager:
        def __init__(self):
            self.completed = asyncio.Event()

        async def kill_owned_sessions(self, _session_id, *, run_id=None):
            assert run_id == "run-1"
            self.completed.set()
            return []

    async def scenario():
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=MemoryStorage(),
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(
                **{**Config.load_template_data()["user_profile"], "enabled": False}
            ),
            recent_summary_config=RecentSummaryConfig(
                **{**Config.load_template_data()["recent_summary"], "enabled": False}
            ),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        manager = RecordingBackgroundProcessManager()
        agent.background_process_manager = manager
        agent.run_state.start("web:browser-1", "run-1")

        async def failing_event(*_args, **_kwargs):
            raise RuntimeError("event transport unavailable")

        agent._emit_run_event = failing_event
        accepted = await agent.request_run_cancel("web:browser-1", "run-1")
        await asyncio.wait_for(manager.completed.wait(), timeout=1)
        return accepted, manager.completed.is_set()

    assert asyncio.run(scenario()) == (True, True)


def test_agent_cancel_request_does_not_orphan_cleanup_when_event_publish_is_cancelled(tmp_path):
    class RecordingBackgroundProcessManager:
        def __init__(self):
            self.completed = asyncio.Event()

        async def kill_owned_sessions(self, _session_id, *, run_id=None):
            assert run_id == "run-1"
            self.completed.set()
            return []

    async def scenario():
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=MemoryStorage(),
            context_builder=FakeContextBuilder(tmp_path / "workspace"),
            tools=ToolRegistry(),
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(
                **{**Config.load_template_data()["user_profile"], "enabled": False}
            ),
            recent_summary_config=RecentSummaryConfig(
                **{**Config.load_template_data()["recent_summary"], "enabled": False}
            ),
            **Config.packaged_agent_llm_chat_kwargs(),
        )
        manager = RecordingBackgroundProcessManager()
        agent.background_process_manager = manager
        agent.run_state.start("web:browser-1", "run-1")
        event_started = asyncio.Event()
        event_release = asyncio.Event()

        async def blocking_event(*_args, **_kwargs):
            event_started.set()
            await event_release.wait()

        agent._emit_run_event = blocking_event
        request = asyncio.create_task(agent.request_run_cancel("web:browser-1", "run-1"))
        await asyncio.wait_for(event_started.wait(), timeout=1)
        await asyncio.wait_for(manager.completed.wait(), timeout=1)
        request.cancel()
        try:
            await request
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancel request did not preserve caller cancellation")

        event_release.set()
        if agent._run_cancel_event_tasks:
            await asyncio.gather(*tuple(agent._run_cancel_event_tasks))
        return manager.completed.is_set()

    assert asyncio.run(scenario()) is True


def test_agent_process_returns_queued_outbound_media(tmp_path):
    async def scenario():
        registry = ToolRegistry()
        registry.register(DummyTool())
        storage = FakeStorage()
        agent = AgentLoop(
            config=Config.load_agent_template_config(),
            provider=FakeProvider(),
            storage=storage,
            context_builder=FakeContextBuilder(tmp_path),
            tools=registry,
            memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
            tools_config=ToolsConfig(),
            log_config=LogConfig(),
            history_search_config=HistorySearchConfig(),
            user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
            **Config.packaged_agent_llm_chat_kwargs(),
        )

        async def fake_call_llm(session_id, current_message, channel=None, user_images=None, allow_tools=True, **kwargs):
            assert media_runtime.queue_outbound_media(agent, "image", "img-out") is None
            assert media_runtime.queue_outbound_media(agent, "voice", "voice-out") is None
            assert media_runtime.queue_outbound_media(agent, "audio", "audio-out") is None
            assert media_runtime.queue_outbound_media(agent, "video", "video-out") is None
            return ExecutionResult(content="sending media", executed_tool_calls=1, used_configure_skill=False)

        async def fake_maintenance(session_id):
            return None

        agent.call_llm = fake_call_llm
        agent._maybe_consolidate_memory = fake_maintenance
        agent._maybe_update_recent_summary = fake_maintenance
        agent._maybe_update_user_profile = fake_maintenance

        response = await agent.process(
            UserMessage(
                text="send it",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
            )
        )
        await agent.wait_for_background_maintenance()
        return response, storage

    response, storage = asyncio.run(scenario())

    assert response.text == "sending media"
    assert response.images == ["img-out"]
    assert response.voices == ["voice-out"]
    assert response.audios == ["audio-out"]
    assert response.videos == ["video-out"]
    assert [entry[1] for entry in storage.saved] == ["user", "assistant"]




def test_background_session_exit_notifier_queues_agent_summary_request(tmp_path):
    registry = ToolRegistry()
    registry.register(DummyTool())
    storage = FakeStorage()
    agent = AgentLoop(
        config=Config.load_agent_template_config(),
        provider=FakeProvider(),
        storage=storage,
        context_builder=FakeContextBuilder(tmp_path),
        tools=registry,
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        **Config.packaged_agent_llm_chat_kwargs(),
    )
    fake_bus = FakeBus()
    agent._message_bus = fake_bus

    class _FakeProcess:
        pid = 4321

    session_token = agent._current_session_id.set("telegram:room-1")
    channel_token = agent._current_channel.set("telegram")
    transport_token = agent._current_external_chat_id.set("room-1")
    try:
        notifier = agent._make_background_session_exit_notifier()
        assert notifier is not None

        session = BackgroundSession(
            session_id="bg123",
            command="python job.py",
            cwd=str(tmp_path),
            process=_FakeProcess(),
            read_tasks=[],
            output_chunks=[CapturedOutputChunk("stdout", b"job done\n")],
            timeout_seconds=5,
            drain_timeout=5,
            state="exited",
            termination_reason="exit",
            exit_code=0,
            started_at=10.0,
            started_at_wall=100.0,
            finished_at=12.5,
            finished_at_wall=102.5,
        )

        asyncio.run(notifier(session))
    finally:
        agent._current_external_chat_id.reset(transport_token)
        agent._current_channel.reset(channel_token)
        agent._current_session_id.reset(session_token)

    assert fake_bus.outbound == []
    assert len(fake_bus.inbound) == 1
    inbound = fake_bus.inbound[0]
    assert inbound.channel == "telegram"
    assert inbound.external_chat_id == "room-1"
    assert inbound.session_id == "telegram:room-1"
    assert inbound.sender_id == "system:background"
    assert "A managed background process has finished." in inbound.content
    assert "Session ID: bg123" in inbound.content
    assert "Command: python job.py" in inbound.content
    assert "job done" in inbound.content
    assert inbound.metadata["kind"] == "background_session_summary_request"
    assert inbound.metadata["_bypass_commands"] is True
    assert storage.saved == []


def test_call_llm_trims_old_history_to_token_budget(tmp_path):
    context_builder = FakeContextBuilder(tmp_path)
    storage = HistoryStorage(
        [
            StoredMessage(role="user", content="old message " * 40, timestamp=1.0),
            StoredMessage(role="assistant", content="recent message", timestamp=2.0),
        ]
    )
    agent = AgentLoop(
        config=Config.load_agent_template_config(history_token_budget=120),
        provider=FakeProvider(),
        storage=storage,
        context_builder=context_builder,
        tools=ToolRegistry(),
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
        **Config.packaged_agent_llm_chat_kwargs(),
    )

    captured = {}

    async def fake_execute_messages(
        log_id,
        chat_messages,
        *,
        allow_tools,
        tool_result_session_id=None,
        tool_registry=None,
        on_tool_before_execute=None,
        on_tool_after_execute=None,
        on_llm_status=None,
        on_response_delta=None,
        on_tool_input_delta=None,
        on_reasoning_delta=None,
        refresh_system_prompt=None,
        max_tool_iterations=None,
        should_cancel=None,
    ):
        captured["messages"] = list(chat_messages)
        return ExecutionResult(content="ok", executed_tool_calls=0, used_configure_skill=False)

    agent._execute_messages = fake_execute_messages

    result = asyncio.run(agent.call_llm("telegram:room-1", "current input", channel="telegram", allow_tools=False))

    assert result.content == "ok"
    assert context_builder.last_history == [{"role": "assistant", "content": "recent message"}]
    assert [message.role for message in captured["messages"]] == ["user"]


def test_load_history_uses_agent_max_history(tmp_path):
    storage = HistoryStorage(
        [
            StoredMessage(role="user", content="first", timestamp=1.0),
            StoredMessage(role="assistant", content="second", timestamp=2.0),
            StoredMessage(role="user", content="third", timestamp=3.0),
        ]
    )
    agent = AgentLoop(
        config=Config.load_agent_template_config(max_history=2),
        provider=FakeProvider(),
        storage=storage,
        context_builder=FakeContextBuilder(tmp_path),
        tools=ToolRegistry(),
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
        **Config.packaged_agent_llm_chat_kwargs(),
    )

    history = asyncio.run(agent._load_history("telegram:room-1"))

    assert [message.content for message in history] == ["second", "third"]


def test_trim_history_reports_base_tokens_without_history(tmp_path):
    agent = AgentLoop(
        config=Config.load_agent_template_config(history_token_budget=500),
        provider=FakeProvider(),
        storage=FakeStorage(),
        context_builder=FakeContextBuilder(tmp_path),
        tools=ToolRegistry(),
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
        **Config.packaged_agent_llm_chat_kwargs(),
    )

    history, base_tokens, history_tokens, final_tokens = agent._trim_history_to_token_budget(
        history=[],
        current_message="hello",
        channel="telegram",
        session_id="telegram:room-1",
    )

    assert history == []
    assert base_tokens > 0
    assert history_tokens == 0
    assert final_tokens == base_tokens


def test_effective_context_budget_uses_model_window_and_manual_cap(tmp_path):
    chat_kwargs = Config.packaged_agent_llm_chat_kwargs()
    chat_kwargs["llm_output_reserve_tokens"] = 200
    agent = AgentLoop(
        config=Config.load_agent_template_config(history_token_budget=1000),
        provider=FakeProvider(),
        storage=FakeStorage(),
        context_builder=FakeContextBuilder(tmp_path),
        tools=ToolRegistry(),
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
        llm_context_window_tokens=500,
        **chat_kwargs,
    )

    assert agent._effective_context_token_budget() == 300
    assert agent.execution_engine.context_compaction_token_budget == 300

    agent.config.history_token_budget = 150
    assert agent._effective_context_token_budget() == 150


def test_tool_schema_tokens_reduce_history_budget(tmp_path):
    storage = HistoryStorage([StoredMessage(role="assistant", content="recent message", timestamp=1.0)])
    registry = ToolRegistry()
    registry.register(LargeSchemaTool())
    agent = AgentLoop(
        config=Config.load_agent_template_config(history_token_budget=150),
        provider=FakeProvider(),
        storage=storage,
        context_builder=FakeContextBuilder(tmp_path),
        tools=registry,
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
        **Config.packaged_agent_llm_chat_kwargs(),
    )

    tool_tokens = agent._estimate_tool_schema_tokens(allow_tools=True)
    assert tool_tokens > 0

    kept_without_tools, _, _, _ = agent._trim_history_to_token_budget(
        history=[{"role": "assistant", "content": "recent message"}],
        current_message="hello",
        channel="telegram",
        session_id="telegram:room-1",
        tool_schema_tokens=0,
    )
    kept_with_tools, _, _, _ = agent._trim_history_to_token_budget(
        history=[{"role": "assistant", "content": "recent message"}],
        current_message="hello",
        channel="telegram",
        session_id="telegram:room-1",
        tool_schema_tokens=tool_tokens,
    )

    assert kept_without_tools == [{"role": "assistant", "content": "recent message"}]
    assert kept_with_tools == []


def test_agent_process_returns_setup_hint_when_llm_not_configured(tmp_path):
    storage = FakeStorage()
    messages = MessagesConfig(**{"agent": {"llm_not_configured": "請先設定 LLM"}})
    agent = AgentLoop(
        config=Config.load_agent_template_config(),
        provider=FakeProvider(),
        storage=storage,
        context_builder=FakeContextBuilder(tmp_path),
        tools=ToolRegistry(),
        memory_config=MemoryConfig(**Config.load_template_data()["memory"]),
        tools_config=ToolsConfig(),
        log_config=LogConfig(),
        history_search_config=HistorySearchConfig(),
        user_profile_config=UserProfileConfig(**{**Config.load_template_data()["user_profile"], "enabled": False}),
        recent_summary_config=RecentSummaryConfig(**{**Config.load_template_data()["recent_summary"], "enabled": False}),
        llm_configured=False,
        messages_config=messages,
        **Config.packaged_agent_llm_chat_kwargs(),
    )

    async def fail_call_llm(*args, **kwargs):
        raise AssertionError("call_llm should not run when llm is not configured")

    agent.call_llm = fail_call_llm

    response = asyncio.run(
        agent.process(
            UserMessage(
                text="hello",
                channel="telegram",
                external_chat_id="room-1",
                session_id="telegram:room-1",
                sender_id="user-1",
                sender_name="alice",
            )
        )
    )

    assert response.text == "請先設定 LLM"
    assert [entry[1] for entry in storage.saved] == ["user", "assistant"]
    assert storage.saved[1][2] == "請先設定 LLM"
