import asyncio
from dataclasses import dataclass

from opensprite.bus.events import RunEvent
from opensprite.bus.dispatcher import MessageQueue
from opensprite.bus.message import AssistantMessage
from opensprite.config.schema import MessagesConfig, ToolsConfig
from opensprite.cron.manager import CronManager
from opensprite.cron.types import CronJob, CronSchedule
from opensprite.llms.base import LLMResponse, ToolCall
from opensprite.runs.events import (
    RUN_PART_DELTA_EVENT,
    TOOL_RESULT_EVENT,
    TOOL_STARTED_EVENT,
)
from opensprite.runs.lifecycle import RUN_FINISHED_EVENT, RUN_STARTED_EVENT
from opensprite.storage import MemoryStorage

from tests.agent.agent_test_helpers import make_agent_loop


class FakeAgent:
    def __init__(self, response_channel: str = "unknown"):
        self.response_channel = response_channel
        self.seen_messages = []

    async def process(self, user_message):
        self.seen_messages.append(user_message)
        return AssistantMessage(
            text="pong",
            channel=self.response_channel,
            external_chat_id=user_message.external_chat_id,
            session_id=user_message.session_id,
        )


class ReplyProvider:
    async def chat(self, messages, tools=None, model=None, temperature=0.7, max_tokens=2048, **kwargs):
        return LLMResponse(content="trace pong", model="fake-model")

    def get_default_model(self) -> str:
        return "fake-model"


@dataclass
class FakeActiveRun:
    run_id: str


class ToolReplyProvider:
    def __init__(self):
        self.responses = [
            LLMResponse(
                content="need tool",
                model="fake-model",
                tool_calls=[ToolCall(id="tc1", name="dummy", arguments={"value": "abc"})],
            ),
            LLMResponse(content="tool trace pong", model="fake-model"),
        ]

    async def chat(self, messages, tools=None, model=None, temperature=0.7, max_tokens=2048, **kwargs):
        return self.responses.pop(0)

    def get_default_model(self) -> str:
        return "fake-model"


async def _run_queue_once(agent_channel: str, inbound_channel: str):
    agent = FakeAgent(response_channel=agent_channel)
    queue = MessageQueue(agent)
    received = []
    event = asyncio.Event()

    async def telegram_handler(message, channel, external_chat_id):
        received.append(("telegram", channel, external_chat_id, message.text))
        event.set()

    async def slack_handler(message, channel, external_chat_id):
        received.append(("slack", channel, external_chat_id, message.text))
        event.set()

    queue.register_response_handler("telegram", telegram_handler)
    queue.register_response_handler("slack", slack_handler)

    processor = asyncio.create_task(queue.process_queue())
    try:
        await queue.enqueue_raw(content="ping", external_chat_id="chat-1", channel=inbound_channel)
        await asyncio.wait_for(event.wait(), timeout=2)
        for _ in range(20):
            if f"{inbound_channel}:chat-1" not in queue._active_tasks:
                break
            await asyncio.sleep(0)
        assert f"{inbound_channel}:chat-1" not in queue._active_tasks
    finally:
        await queue.stop()
        await asyncio.wait_for(processor, timeout=2)

    return received, agent.seen_messages


def test_message_queue_routes_response_to_explicit_channel_handler():
    received, seen_messages = asyncio.run(_run_queue_once(agent_channel="slack", inbound_channel="telegram"))

    assert received == [("slack", "slack", "chat-1", "pong")]
    assert seen_messages[0].session_id == "telegram:chat-1"


def test_message_queue_falls_back_to_inbound_channel_when_response_channel_unknown():
    received, _ = asyncio.run(_run_queue_once(agent_channel="unknown", inbound_channel="telegram"))

    assert received == [("telegram", "telegram", "chat-1", "pong")]


def test_command_detection_ignores_empty_text():
    assert MessageQueue.is_help_command("") is False
    assert MessageQueue.is_stop_command("") is False
    assert MessageQueue.is_stop_command("   ") is False
    assert MessageQueue.is_reset_command("") is False
    assert MessageQueue.is_cron_command("") is False


def test_help_command_detection_supports_mentions_and_args():
    assert MessageQueue.is_help_command("/help") is True
    assert MessageQueue.is_help_command("/help cron") is True
    assert MessageQueue.is_help_command("/help@OpenSpriteBot task") is True
    assert MessageQueue.is_help_command("help") is False


def test_message_queue_help_command_publishes_registry_help_without_calling_agent():
    async def scenario():
        agent = FakeAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((channel, external_chat_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/help", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses[0][0] == "telegram"
    assert responses[0][1] == "same-chat"
    assert "Available chat commands:" in responses[0][2]
    assert "/help [command]" in responses[0][2]
    assert "/cron <subcommand>" in responses[0][2]


def test_message_queue_help_command_can_delegate_to_cron_help_text():
    async def scenario():
        agent = FakeAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append(message.text)
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/help cron", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses
    assert "/cron add every <seconds> <message> [--no-deliver]" in responses[0]
    assert "/cron help" in responses[0]


def test_message_queue_help_overview_lists_curator_command():
    async def scenario():
        agent = FakeAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append(message.text)
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/help", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses
    assert "/curator <status|history [limit]|run [scope]|pause|resume|help>" in responses[0]


def test_curator_status_command_replies_immediately_without_running_agent_loop():
    class CuratorAgent(FakeAgent):
        async def get_curator_status(self, session_id):
            return {
                "session_id": session_id,
                "state": "idle",
                "running": False,
                "queued": False,
                "rerun_pending": False,
                "jobs": [],
                "run_id": None,
            }

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator status", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses == [
        (
            "telegram:same-chat",
            "Curator 狀態:\n- 狀態: idle\n- 已暫停: no\n- 執行次數: 0\n- 上次執行: never\n- 上次摘要: none\n- 待補跑: no\n- 工作: none",
        )
    ]


def test_curator_status_command_includes_current_job_and_last_changed_when_available():
    class CuratorAgent(FakeAgent):
        async def get_curator_status(self, session_id):
            return {
                "session_id": session_id,
                "state": "running",
                "running": True,
                "queued": False,
                "paused": False,
                "rerun_pending": False,
                "jobs": ["memory", "skills"],
                "current_job": "memory",
                "current_job_label": "memory",
                "run_count": 3,
                "last_run_at": "2026-05-01T00:00:00Z",
                "last_run_jobs": ["memory", "skills"],
                "last_run_changed": ["memory"],
                "last_run_summary": "Updated memory.",
            }

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append(message.text)
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator status", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses
    assert "- 目前工作: memory" in responses[0]
    assert "- 上次工作: memory, skills" in responses[0]
    assert "- 上次變更: memory" in responses[0]


def test_curator_history_command_renders_recent_runs():
    class CuratorAgent(FakeAgent):
        async def get_curator_history(self, session_id, *, limit=10):
            assert session_id == "telegram:same-chat"
            assert limit == 2
            return [
                {
                    "run_id": "run-2",
                    "run_at": "2026-05-01T00:00:02Z",
                    "jobs": ["skills"],
                    "changed": ["skills"],
                    "summary": "Updated skills.",
                    "error": None,
                    "status": "completed",
                },
                {
                    "run_id": "run-1",
                    "run_at": "2026-05-01T00:00:01Z",
                    "jobs": ["memory"],
                    "changed": [],
                    "summary": "Curator failed: memory broke",
                    "error": "memory broke",
                    "status": "failed",
                },
            ]

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append(message.text)
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator history 2", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses
    assert "Curator 歷史:" in responses[0]
    assert "#1 2026-05-01T00:00:02Z (completed)" in responses[0]
    assert "- 工作: skills" in responses[0]
    assert "- 摘要: Updated skills." in responses[0]
    assert "#2 2026-05-01T00:00:01Z (failed)" in responses[0]
    assert "- 錯誤: memory broke" in responses[0]


def test_curator_history_command_rejects_invalid_limit():
    async def scenario():
        agent = FakeAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append(message.text)
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator history nope", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses == ["Error: limit must be a positive integer. Usage: /curator history [limit]"]


def test_curator_run_command_replies_immediately_without_running_agent_loop():
    class CuratorAgent(FakeAgent):
        async def run_curator_now(self, session_id, *, scope=None, channel=None, external_chat_id=None):
            assert scope is None
            return {
                "session_id": session_id,
                "state": "running",
                "running": True,
                "queued": False,
                "rerun_pending": False,
                "jobs": ["memory", "recent_summary", "user_profile", "skills"],
                "run_id": "run-123",
                "scheduled": True,
            }

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator run", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses == [
        (
            "telegram:same-chat",
            "已排入背景整理。\n\nCurator 狀態:\n- 狀態: running\n- 已暫停: no\n- 執行次數: 0\n- 上次執行: never\n- 上次摘要: none\n- 待補跑: no\n- 工作: memory, recent_summary, user_profile, skills\n- 關聯 run: run-123",
        )
    ]


def test_curator_run_command_accepts_scope_argument():
    class CuratorAgent(FakeAgent):
        async def run_curator_now(self, session_id, *, scope=None, channel=None, external_chat_id=None):
            assert scope == "memory"
            return {
                "session_id": session_id,
                "state": "queued",
                "running": False,
                "queued": True,
                "rerun_pending": False,
                "jobs": ["memory"],
                "run_id": "run-456",
                "scheduled": True,
            }

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append(message.text)
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator run memory", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses
    assert "- 工作: memory" in responses[0]


def test_curator_run_command_rejects_invalid_scope():
    async def scenario():
        agent = FakeAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append(message.text)
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator run nope", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses == [
        "Unknown curator scope: nope. Valid scopes: maintenance, skills, memory, recent_summary, user_profile"
    ]


def test_curator_pause_command_replies_immediately_without_running_agent_loop():
    class CuratorAgent(FakeAgent):
        async def pause_curator(self, session_id):
            return {
                "session_id": session_id,
                "state": "paused",
                "running": False,
                "queued": False,
                "paused": True,
                "rerun_pending": False,
                "jobs": [],
                "run_id": None,
            }

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator pause", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses == [
        (
            "telegram:same-chat",
            "已暫停背景整理。\n\nCurator 狀態:\n- 狀態: paused\n- 已暫停: yes\n- 執行次數: 0\n- 上次執行: never\n- 上次摘要: none\n- 待補跑: no\n- 工作: none",
        )
    ]


def test_curator_resume_command_replies_immediately_without_running_agent_loop():
    class CuratorAgent(FakeAgent):
        async def resume_curator(self, session_id):
            return {
                "session_id": session_id,
                "state": "idle",
                "running": False,
                "queued": False,
                "paused": False,
                "rerun_pending": False,
                "jobs": [],
                "run_id": None,
            }

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator resume", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses == [
        (
            "telegram:same-chat",
            "已恢復背景整理。\n\nCurator 狀態:\n- 狀態: idle\n- 已暫停: no\n- 執行次數: 0\n- 上次執行: never\n- 上次摘要: none\n- 待補跑: no\n- 工作: none",
        )
    ]


def test_curator_run_command_reports_paused_status_when_manual_run_is_blocked():
    class CuratorAgent(FakeAgent):
        async def run_curator_now(self, session_id, *, scope=None, channel=None, external_chat_id=None):
            assert scope is None
            return {
                "session_id": session_id,
                "state": "paused",
                "running": False,
                "queued": False,
                "paused": True,
                "rerun_pending": False,
                "jobs": [],
                "run_id": None,
                "scheduled": False,
            }

    async def scenario():
        agent = CuratorAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/curator run", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert seen_messages == []
    assert responses == [
        (
            "telegram:same-chat",
            "背景整理目前已暫停，請先恢復。\n\nCurator 狀態:\n- 狀態: paused\n- 已暫停: yes\n- 執行次數: 0\n- 上次執行: never\n- 上次摘要: none\n- 待補跑: no\n- 工作: none",
        )
    ]


def test_message_queue_accepts_empty_text_media_message():
    async def scenario():
        agent = FakeAgent(response_channel="telegram")
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="", external_chat_id="media-chat", channel="telegram", images=["img-a"])
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert responses == [("telegram:media-chat", "pong")]
    assert seen_messages[0].text == ""
    assert seen_messages[0].images == ["img-a"]


def test_message_queue_tracks_session_status_during_processing():
    class BlockingAgent(FakeAgent):
        def __init__(self):
            super().__init__(response_channel="telegram")
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def process(self, user_message):
            self.started.set()
            await self.release.wait()
            return await super().process(user_message)

    async def scenario():
        agent = BlockingAgent()
        queue = MessageQueue(agent)
        response_sent = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            response_sent.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="ping", external_chat_id="status-chat", channel="telegram")
            await asyncio.wait_for(agent.started.wait(), timeout=2)
            thinking = queue.session_status.get("telegram:status-chat")
            listed = queue.session_status.list()
            agent.release.set()
            await asyncio.wait_for(response_sent.wait(), timeout=2)
            idle = queue.session_status.get("telegram:status-chat")
            final_list = queue.session_status.list()
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return thinking, listed, idle, final_list

    thinking, listed, idle, final_list = asyncio.run(scenario())

    assert thinking.status == "thinking"
    assert thinking.metadata == {"channel": "telegram", "external_chat_id": "status-chat"}
    assert [item.session_id for item in listed] == ["telegram:status-chat"]
    assert idle.status == "idle"
    assert idle.session_id == "telegram:status-chat"
    assert final_list == []


def test_message_queue_maps_run_events_to_granular_session_status():
    async def scenario():
        queue = MessageQueue(FakeAgent())
        event = RunEvent(
            channel="web",
            external_chat_id="browser-1",
            session_id="web:browser-1",
            run_id="run-1",
            event_type=RUN_STARTED_EVENT,
        )
        await queue._set_session_status_from_run_event(event)
        thinking = queue.session_status.get("web:browser-1")

        await queue._set_session_status_from_run_event(
            RunEvent(
                channel="web",
                external_chat_id="browser-1",
                session_id="web:browser-1",
                run_id="run-1",
                event_type=RUN_PART_DELTA_EVENT,
                payload={"content_delta": "hi"},
            )
        )
        streaming = queue.session_status.get("web:browser-1")

        await queue._set_session_status_from_run_event(
            RunEvent(
                channel="web",
                external_chat_id="browser-1",
                session_id="web:browser-1",
                run_id="run-1",
                event_type=TOOL_STARTED_EVENT,
                payload={"tool_name": "demo"},
            )
        )
        tool_running = queue.session_status.get("web:browser-1")

        await queue._set_session_status_from_run_event(
            RunEvent(
                channel="web",
                external_chat_id="browser-1",
                session_id="web:browser-1",
                run_id="run-1",
                event_type="llm_status",
                payload={"status": "retry", "message": "provider busy"},
            )
        )
        retry = queue.session_status.get("web:browser-1")

        await queue._set_session_status_from_run_event(
            RunEvent(
                channel="web",
                external_chat_id="browser-1",
                session_id="web:browser-1",
                run_id="run-1",
                event_type=RUN_FINISHED_EVENT,
            )
        )
        idle = queue.session_status.get("web:browser-1")
        return thinking, streaming, tool_running, retry, idle

    thinking, streaming, tool_running, retry, idle = asyncio.run(scenario())

    assert thinking.status == "thinking"
    assert thinking.metadata["run_id"] == "run-1"
    assert streaming.status == "streaming"
    assert tool_running.status == "tool_running"
    assert tool_running.metadata["tool_name"] == "demo"
    assert retry.status == "retry"
    assert retry.metadata["message"] == "provider busy"
    assert idle.status == "idle"


def test_message_queue_cancel_session_requests_active_run_cancel_first():
    class CancellableAgent(FakeAgent):
        def __init__(self):
            super().__init__(response_channel="telegram")
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.cancel_calls = []
            self.active_by_session = {}

        def get_active_run(self, session_id):
            return self.active_by_session.get(session_id)

        async def request_run_cancel(self, session_id, run_id, *, channel=None, external_chat_id=None):
            self.cancel_calls.append((session_id, run_id, channel, external_chat_id))
            return True

        async def process(self, user_message):
            self.active_by_session[user_message.session_id] = FakeActiveRun("run-active")
            self.started.set()
            try:
                await self.release.wait()
                return await super().process(user_message)
            finally:
                self.active_by_session.pop(user_message.session_id, None)

    async def scenario():
        agent = CancellableAgent()
        queue = MessageQueue(agent)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="ping", external_chat_id="cancel-chat", channel="telegram")
            await asyncio.wait_for(agent.started.wait(), timeout=2)
            cancelled = await queue.cancel_session("telegram:cancel-chat")
            status = queue.session_status.get("telegram:cancel-chat")
        finally:
            agent.release.set()
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return cancelled, status, agent.cancel_calls

    cancelled, status, cancel_calls = asyncio.run(scenario())

    assert cancelled == 1
    assert status.status == "idle"
    assert cancel_calls == [("telegram:cancel-chat", "run-active", "telegram", "cancel-chat")]


def test_message_queue_counts_successful_cooperative_cancel_even_when_task_finishes_late():
    class FinishingAgent(FakeAgent):
        def get_active_run(self, _session_id):
            return FakeActiveRun("run-active")

        async def request_run_cancel(self, *args, **kwargs):
            return True

    async def finish_after_cancel(started):
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            return "completed"

    async def scenario():
        started = asyncio.Event()
        queue = MessageQueue(FinishingAgent(response_channel="telegram"))
        task = asyncio.create_task(finish_after_cancel(started))
        queue._active_tasks["telegram:cancel-chat"] = [task]
        await started.wait()
        cancelled = await queue.cancel_session("telegram:cancel-chat")
        return cancelled, task.result(), queue.session_status.get("telegram:cancel-chat")

    cancelled, result, status = asyncio.run(scenario())

    assert cancelled == 1
    assert result == "completed"
    assert status.status == "idle"


def test_message_queue_stop_fences_messages_still_waiting_in_inbound_queue():
    async def scenario():
        agent = FakeAgent(response_channel="telegram")
        queue = MessageQueue(agent)
        received = asyncio.Event()

        async def handler(*_args):
            received.set()

        queue.register_response_handler("telegram", handler)
        await queue.enqueue_raw(content="stale", external_chat_id="stop-chat", channel="telegram")
        cancelled = await queue.cancel_session("telegram:stop-chat")

        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="fresh", external_chat_id="stop-chat", channel="telegram")
            await asyncio.wait_for(received.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
        return cancelled, [message.text for message in agent.seen_messages]

    cancelled, seen = asyncio.run(scenario())

    assert cancelled == 1
    assert seen == ["fresh"]


def test_message_queue_cancels_all_session_tails_before_any_later_tail_can_start():
    class TailAgent(FakeAgent):
        def __init__(self):
            super().__init__(response_channel="telegram")
            self.first_started = asyncio.Event()

        async def process(self, user_message):
            self.seen_messages.append(user_message)
            if user_message.text == "first":
                self.first_started.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    return AssistantMessage(
                        text="finished during cancellation",
                        channel="telegram",
                        external_chat_id=user_message.external_chat_id,
                        session_id=user_message.session_id,
                    )
            return AssistantMessage(
                text="unexpected later tail",
                channel="telegram",
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
            )

    async def scenario():
        agent = TailAgent()
        queue = MessageQueue(agent)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="first", external_chat_id="tail-chat", channel="telegram")
            await asyncio.wait_for(agent.first_started.wait(), timeout=2)
            await queue.enqueue_raw(content="second", external_chat_id="tail-chat", channel="telegram")
            await queue.enqueue_raw(content="third", external_chat_id="tail-chat", channel="telegram")
            for _ in range(50):
                if len(queue._active_tasks.get("telegram:tail-chat", [])) == 3:
                    break
                await asyncio.sleep(0)
            cancelled = await queue.cancel_session("telegram:tail-chat")
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
        return cancelled, [message.text for message in agent.seen_messages]

    cancelled, seen = asyncio.run(scenario())

    assert cancelled == 3
    assert seen == ["first"]


def test_message_queue_waits_for_cancelled_tail_cleanup_before_starting_fresh_generation():
    class CleanupRaceAgent(FakeAgent):
        def __init__(self):
            super().__init__(response_channel="telegram")
            self.first_started = asyncio.Event()
            self.cancellation_seen = asyncio.Event()
            self.release_cleanup = asyncio.Event()
            self.fresh_attempted = asyncio.Event()
            self.run_active = False

        def get_active_run(self, _session_id):
            return FakeActiveRun(run_id="run-1") if self.run_active else None

        async def request_run_cancel(self, *_args, **_kwargs):
            return True

        async def process(self, user_message):
            if user_message.text == "first":
                self.run_active = True
                self.first_started.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    self.cancellation_seen.set()
                    await self.release_cleanup.wait()
                    self.run_active = False
                    raise

            self.fresh_attempted.set()
            if self.run_active:
                raise RuntimeError("run is still active")
            self.seen_messages.append(user_message)
            return AssistantMessage(
                text="fresh pong",
                channel="telegram",
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
            )

    async def scenario():
        agent = CleanupRaceAgent()
        queue = MessageQueue(agent)
        responses = []
        response_received = asyncio.Event()

        async def handler(message, *_args):
            responses.append(message.text)
            response_received.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        cancel_task = None
        try:
            await queue.enqueue_raw(content="first", external_chat_id="race-chat", channel="telegram")
            await asyncio.wait_for(agent.first_started.wait(), timeout=2)

            cancel_task = asyncio.create_task(queue.cancel_session("telegram:race-chat"))
            await asyncio.wait_for(agent.cancellation_seen.wait(), timeout=2)
            await queue.enqueue_raw(content="fresh", external_chat_id="race-chat", channel="telegram")

            try:
                await asyncio.wait_for(agent.fresh_attempted.wait(), timeout=0.1)
                started_before_cleanup = True
            except asyncio.TimeoutError:
                started_before_cleanup = False

            agent.release_cleanup.set()
            cancelled = await asyncio.wait_for(cancel_task, timeout=2)
            await asyncio.wait_for(response_received.wait(), timeout=2)
            return (
                cancelled,
                started_before_cleanup,
                [message.text for message in agent.seen_messages],
                responses,
            )
        finally:
            agent.release_cleanup.set()
            if cancel_task is not None and not cancel_task.done():
                await asyncio.wait_for(cancel_task, timeout=2)
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

    cancelled, started_before_cleanup, seen, responses = asyncio.run(scenario())

    assert cancelled == 1
    assert started_before_cleanup is False
    assert seen == ["fresh"]
    assert responses == ["fresh pong"]


def test_message_queue_persists_run_trace_for_telegram_message(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=ReplyProvider(), storage=storage)
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, channel, external_chat_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="trace ping", external_chat_id="trace-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        session_id = "telegram:trace-chat"
        runs = await storage.get_runs(session_id)
        assert len(runs) == 1
        run = runs[0]
        events = await storage.get_run_events(session_id, run.run_id)
        parts = await storage.get_run_parts(session_id, run.run_id)
        return responses, run, events, parts

    responses, run, events, parts = asyncio.run(scenario())

    assert responses == [("telegram:trace-chat", "telegram", "trace-chat", "trace pong")]
    assert run.session_id == "telegram:trace-chat"
    assert run.status == "completed"
    assert run.metadata["channel"] == "telegram"
    assert run.metadata["external_chat_id"] == "trace-chat"
    event_types = [event.event_type for event in events]
    assert RUN_STARTED_EVENT in event_types
    assert RUN_FINISHED_EVENT in event_types
    assert events[0].payload["status"] == "running"
    assert events[-1].payload["status"] == "completed"
    assert [part.part_type for part in parts] == [
        "llm_step",
        "assistant_message",
    ]
    assert parts[-1].content == "trace pong"


def test_message_queue_persists_tool_trace_for_telegram_message(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        agent = make_agent_loop(tmp_path, provider=ToolReplyProvider(), storage=storage)
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, channel, external_chat_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="use a tool", external_chat_id="tool-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        session_id = "telegram:tool-chat"
        runs = await storage.get_runs(session_id)
        assert len(runs) == 1
        run = runs[0]
        events = await storage.get_run_events(session_id, run.run_id)
        parts = await storage.get_run_parts(session_id, run.run_id)
        return responses, run, events, parts

    responses, run, events, parts = asyncio.run(scenario())

    assert responses == [("telegram:tool-chat", "telegram", "tool-chat", "tool trace pong")]
    assert run.status == "completed"
    assert run.metadata["executed_tool_calls"] == 1
    event_types = [event.event_type for event in events]
    assert TOOL_STARTED_EVENT in event_types
    assert TOOL_RESULT_EVENT in event_types
    assert RUN_FINISHED_EVENT in event_types
    tool_events = [event for event in events if event.event_type in {TOOL_STARTED_EVENT, TOOL_RESULT_EVENT}]
    assert [event.payload["tool_name"] for event in tool_events] == ["dummy", "dummy"]
    part_types = [part.part_type for part in parts]
    assert part_types[:4] == ["tool_call", "tool_result", "llm_step", "llm_step"]
    assert any(part.part_type == "assistant_message" and part.content == "tool trace pong" for part in parts)
    tool_parts = [part for part in parts if part.part_type in {"tool_call", "tool_result"}]
    assert [part.tool_name for part in tool_parts] == ["dummy", "dummy"]
    assert tool_parts[0].metadata["tool_call_id"] == "tc1"
    assert tool_parts[0].metadata["state"] == "running"
    assert tool_parts[1].metadata["tool_call_id"] == "tc1"
    assert tool_parts[1].metadata["ok"] is True
    assert tool_parts[1].content == "ok"


def test_message_queue_can_bypass_immediate_commands_for_internal_messages():
    async def scenario():
        agent = FakeAgent(response_channel="telegram")
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(
                content="/cron help",
                external_chat_id="same-chat",
                channel="telegram",
                metadata={"_bypass_commands": True, "source": "cron"},
            )
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert responses == [("telegram:same-chat", "pong")]
    assert seen_messages[0].text == "/cron help"
    assert seen_messages[0].metadata == {"source": "cron"}


def test_message_queue_can_suppress_final_outbound_for_internal_messages():
    class EventAgent(FakeAgent):
        def __init__(self):
            super().__init__(response_channel="telegram")
            self.done = asyncio.Event()

        async def process(self, user_message):
            response = await super().process(user_message)
            self.done.set()
            return response

    async def scenario():
        agent = EventAgent()
        queue = MessageQueue(agent)
        responses = []

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(
                content="quiet cron",
                external_chat_id="same-chat",
                channel="telegram",
                metadata={"_suppress_outbound": True, "source": "cron"},
            )
            await asyncio.wait_for(agent.done.wait(), timeout=2)
            await asyncio.sleep(0.05)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.seen_messages

    responses, seen_messages = asyncio.run(scenario())

    assert responses == []
    assert seen_messages[0].text == "quiet cron"
    assert seen_messages[0].metadata == {"source": "cron"}


def test_message_queue_processor_exits_cleanly_when_cancelled_while_idle():
    async def scenario():
        queue = MessageQueue(FakeAgent())
        processor = asyncio.create_task(queue.process_queue())
        await asyncio.sleep(0)

        processor.cancel()
        await asyncio.wait_for(processor, timeout=2)

    asyncio.run(scenario())


class SequencingAgent:
    def __init__(self):
        self.events = []
        self.concurrent_sessions = 0
        self.max_concurrent_sessions = 0
        self._same_session_running = False

    async def process(self, user_message):
        session_id = user_message.session_id
        if session_id == "telegram:same-chat":
            assert self._same_session_running is False
            self._same_session_running = True
            self.events.append(("start", user_message.text))
            await asyncio.sleep(0.05)
            self.events.append(("finish", user_message.text))
            self._same_session_running = False
        else:
            self.concurrent_sessions += 1
            self.max_concurrent_sessions = max(self.max_concurrent_sessions, self.concurrent_sessions)
            self.events.append(("start", session_id, user_message.text))
            await asyncio.sleep(0.05)
            self.events.append(("finish", session_id, user_message.text))
            self.concurrent_sessions -= 1

        return AssistantMessage(
            text=f"done:{user_message.text}",
            channel=user_message.channel,
            external_chat_id=user_message.external_chat_id,
            session_id=user_message.session_id,
        )


async def _run_queue_for_serialization(enqueue_actions):
    agent = SequencingAgent()
    queue = MessageQueue(agent)
    responses = []
    event = asyncio.Event()

    async def handler(message, channel, external_chat_id):
        responses.append((message.session_id, message.text))
        if len(responses) == len(enqueue_actions):
            event.set()

    queue.register_response_handler("telegram", handler)
    processor = asyncio.create_task(queue.process_queue())
    try:
        for kwargs in enqueue_actions:
            await queue.enqueue_raw(**kwargs)
        await asyncio.wait_for(event.wait(), timeout=2)
    finally:
        await queue.stop()
        await asyncio.wait_for(processor, timeout=2)

    return agent, responses


def test_message_queue_serializes_processing_within_the_same_session():
    agent, responses = asyncio.run(
        _run_queue_for_serialization(
            [
                {"content": "first", "external_chat_id": "same-chat", "channel": "telegram"},
                {"content": "second", "external_chat_id": "same-chat", "channel": "telegram"},
            ]
        )
    )

    assert agent.events == [
        ("start", "first"),
        ("finish", "first"),
        ("start", "second"),
        ("finish", "second"),
    ]
    assert responses == [
        ("telegram:same-chat", "done:first"),
        ("telegram:same-chat", "done:second"),
    ]


def test_message_queue_keeps_different_sessions_parallel():
    agent, responses = asyncio.run(
        _run_queue_for_serialization(
            [
                {"content": "first", "external_chat_id": "chat-a", "channel": "telegram"},
                {"content": "second", "external_chat_id": "chat-b", "channel": "telegram"},
            ]
        )
    )

    assert agent.max_concurrent_sessions >= 2
    assert sorted(responses) == [
        ("telegram:chat-a", "done:first"),
        ("telegram:chat-b", "done:second"),
    ]


class StoppableAgent:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def process(self, user_message):
        self.started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        return AssistantMessage(
            text="should-not-happen",
            channel=user_message.channel,
            external_chat_id=user_message.external_chat_id,
            session_id=user_message.session_id,
        )


def test_stop_command_cancels_running_session_and_replies_immediately():
    async def scenario():
        agent = StoppableAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="long task", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(agent.started.wait(), timeout=2)
            await queue.enqueue_raw(content="/stop", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
            await asyncio.wait_for(agent.cancelled.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses == [("telegram:same-chat", "已停止目前這段對話。")]


def test_stop_command_reports_when_nothing_is_running():
    async def scenario():
        queue = MessageQueue(FakeAgent())
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/stop", external_chat_id="idle-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses == [("telegram:idle-chat", "目前沒有正在執行的對話可停止。")]


def test_stop_command_uses_configured_idle_message():
    async def scenario():
        agent = FakeAgent()
        agent.messages = MessagesConfig(**{"queue": {"stop_idle": "目前沒有可停止的任務。"}})
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/stop", external_chat_id="idle-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses == [("telegram:idle-chat", "目前沒有可停止的任務。")]


def test_reset_command_clears_session_history_and_replies_immediately():
    class ResettableAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.reset_calls = []

        async def reset_history(self, session_id):
            self.reset_calls.append(session_id)

    async def scenario():
        agent = ResettableAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/reset", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.reset_calls

    responses, reset_calls = asyncio.run(scenario())

    assert reset_calls == ["telegram:same-chat"]
    assert responses == [("telegram:same-chat", "已重置目前這段對話。")]


def test_reset_command_cancels_running_session_before_clearing_history():
    class ResettableStoppableAgent(StoppableAgent):
        def __init__(self):
            super().__init__()
            self.reset_calls = []

        async def reset_history(self, session_id):
            self.reset_calls.append(session_id)
            assert self.cancelled.is_set() is True

    async def scenario():
        agent = ResettableStoppableAgent()
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="long task", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(agent.started.wait(), timeout=2)
            await queue.enqueue_raw(content="/reset", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
            await asyncio.wait_for(agent.cancelled.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses, agent.reset_calls

    responses, reset_calls = asyncio.run(scenario())

    assert reset_calls == ["telegram:same-chat"]
    assert responses == [("telegram:same-chat", "已重置目前這段對話。 進行中的任務也已停止。")]


def test_cron_command_lists_jobs_for_current_session(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        service = await agent.cron_manager.get_or_create_service("telegram:same-chat")
        service.add_job(
            name="weather-check",
            schedule=CronSchedule(kind="every", every_ms=300_000),
            message="Check weather",
            deliver=True,
            channel="telegram",
            external_chat_id="same-chat",
        )

        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/cron list", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses

    responses = asyncio.run(scenario())

    assert len(responses) == 1
    assert responses[0][0] == "telegram:same-chat"
    assert "Scheduled jobs:" in responses[0][1]
    assert "weather-check" in responses[0][1]


def test_cron_help_uses_configured_messages():
    async def scenario():
        agent = FakeAgent()
        agent.messages = MessagesConfig(**{"cron": {"help_text": "自訂排程說明"}})
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/cron help", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert responses == [("telegram:same-chat", "自訂排程說明")]


def test_cron_command_adds_interval_job_for_current_session(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(
                content='/cron add every 300 "Check weather and report back"',
                external_chat_id="same-chat",
                channel="telegram",
            )
            await asyncio.wait_for(event.wait(), timeout=2)
            service = await agent.cron_manager.get_or_create_service("telegram:same-chat")
            jobs = service.list_jobs(include_disabled=True)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses, jobs

    responses, jobs = asyncio.run(scenario())

    assert len(responses) == 1
    assert "Created job 'Check weather and report back'" in responses[0][1]
    assert len(jobs) == 1
    assert jobs[0].schedule.kind == "every"
    assert jobs[0].schedule.every_ms == 300_000
    assert jobs[0].payload.message == "Check weather and report back"


def test_cron_command_uses_configured_default_timezone_for_cron_expression(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None
            self.tools_config = ToolsConfig(**{"cron": {"default_timezone": "Asia/Taipei"}})

    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(
                content='/cron add cron "0 9 * * *" "Daily report"',
                external_chat_id="same-chat",
                channel="telegram",
            )
            await asyncio.wait_for(event.wait(), timeout=2)
            service = await agent.cron_manager.get_or_create_service("telegram:same-chat")
            jobs = service.list_jobs(include_disabled=True)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses, jobs

    responses, jobs = asyncio.run(scenario())

    assert "Created job 'Daily report'" in responses[0][1]
    assert jobs[0].schedule.kind == "cron"
    assert jobs[0].schedule.tz == "Asia/Taipei"


def test_cron_command_adds_one_time_job_without_delivery_when_requested(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(
                content='/cron add at 2026-04-10T09:00:00 --no-deliver "Remind me later"',
                external_chat_id="same-chat",
                channel="telegram",
            )
            await asyncio.wait_for(event.wait(), timeout=2)
            service = await agent.cron_manager.get_or_create_service("telegram:same-chat")
            jobs = service.list_jobs(include_disabled=True)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses, jobs

    responses, jobs = asyncio.run(scenario())

    assert len(responses) == 1
    assert "Created job 'Remind me later'" in responses[0][1]
    assert len(jobs) == 1
    assert jobs[0].schedule.kind == "at"
    assert jobs[0].payload.deliver is False
    assert jobs[0].delete_after_run is True


def test_cron_command_removes_job_for_current_session(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        service = await agent.cron_manager.get_or_create_service("telegram:same-chat")
        job = service.add_job(
            name="cleanup",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            message="Cleanup",
            deliver=True,
            channel="telegram",
            external_chat_id="same-chat",
        )

        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content=f"/cron remove {job.id}", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
            remaining = service.list_jobs(include_disabled=True)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses, remaining, job.id

    responses, remaining, job_id = asyncio.run(scenario())

    assert responses == [("telegram:same-chat", f"Removed job {job_id}")]
    assert remaining == []


def test_cron_command_can_pause_and_enable_job_for_current_session(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        service = await agent.cron_manager.get_or_create_service("telegram:same-chat")
        job = service.add_job(
            name="cleanup",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            message="Cleanup",
            deliver=True,
            channel="telegram",
            external_chat_id="same-chat",
        )

        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            if len(responses) == 2:
                event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content=f"/cron pause {job.id}", external_chat_id="same-chat", channel="telegram")
            await queue.enqueue_raw(content=f"/cron enable {job.id}", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
            refreshed = service.get_job(job.id)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses, refreshed

    responses, refreshed = asyncio.run(scenario())

    assert responses == [
        ("telegram:same-chat", f"Paused job {refreshed.id}"),
        ("telegram:same-chat", f"Enabled job {refreshed.id}"),
    ]
    assert refreshed is not None
    assert refreshed.enabled is True
    assert refreshed.state.next_run_at_ms is not None


def test_cron_command_can_run_job_for_current_session(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    executions = []

    async def on_job(session_id: str, job: CronJob):
        executions.append((session_id, job.id))
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        service = await agent.cron_manager.get_or_create_service("telegram:same-chat")
        job = service.add_job(
            name="cleanup",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            message="Cleanup",
            deliver=True,
            channel="telegram",
            external_chat_id="same-chat",
        )

        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content=f"/cron run {job.id}", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses, job.id

    responses, job_id = asyncio.run(scenario())

    assert responses == [("telegram:same-chat", f"Ran job {job_id}")]
    assert executions == [("telegram:same-chat", job_id)]


def test_cron_command_help_is_immediate():
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    async def scenario():
        queue = MessageQueue(CronAgent())
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/cron help", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

        return responses

    responses = asyncio.run(scenario())

    assert len(responses) == 1
    assert "/cron list" in responses[0][1]
    assert "/cron pause <job_id>" in responses[0][1]
    assert "/cron enable <job_id>" in responses[0][1]
    assert "/cron run <job_id>" in responses[0][1]
    assert "/cron remove <job_id>" in responses[0][1]


def test_cron_command_reports_invalid_add_usage(tmp_path):
    class CronAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.cron_manager = None

    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        agent = CronAgent()
        agent.cron_manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        queue = MessageQueue(agent)
        responses = []
        event = asyncio.Event()

        async def handler(message, channel, external_chat_id):
            responses.append((message.session_id, message.text))
            event.set()

        queue.register_response_handler("telegram", handler)
        processor = asyncio.create_task(queue.process_queue())
        try:
            await queue.enqueue_raw(content="/cron add every nope broken", external_chat_id="same-chat", channel="telegram")
            await asyncio.wait_for(event.wait(), timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
            await agent.cron_manager.stop()

        return responses

    responses = asyncio.run(scenario())

    assert len(responses) == 1
    assert "Error: every requires an integer number of seconds" in responses[0][1]
