import asyncio

from typer.testing import CliRunner

from opensprite.bus import RunEvent
from opensprite.bus.dispatcher import MessageQueue
from opensprite.bus.message import AssistantMessage
from opensprite.channels.cli import CliAdapter
from opensprite.cli import commands
from opensprite.cli.commands_chat import result_payload


class FakeAgent:
    messages = None
    _message_bus = None

    async def process(self, user_message):
        await self._message_bus.publish_run_event(
            RunEvent(
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                run_id="run-cli",
                event_type="run_started",
                payload={"status": "running"},
                created_at=1.0,
            )
        )
        await self._message_bus.publish_run_event(
            RunEvent(
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                run_id="run-cli",
                event_type="tool_started",
                payload={"tool_name": "web_search"},
                created_at=2.0,
            )
        )
        await self._message_bus.publish_run_event(
            RunEvent(
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                run_id="run-cli",
                event_type="run_finished",
                payload={"status": "completed"},
                created_at=3.0,
            )
        )
        return AssistantMessage(
            text=f"echo:{user_message.text}",
            channel=user_message.channel,
            external_chat_id=user_message.external_chat_id,
            session_id=user_message.session_id,
        )


def test_cli_adapter_runs_one_message_through_queue():
    async def scenario():
        queue = MessageQueue(FakeAgent())
        processor = asyncio.create_task(queue.process_queue())
        adapter = CliAdapter(queue, external_chat_id="smoke")
        try:
            result = await adapter.run_once("ping", timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)
        return result

    result = asyncio.run(scenario())

    assert result.response.text == "echo:ping"
    assert result.response.session_id == "cli:smoke"
    assert result.run_id == "run-cli"
    assert result.run_status == "completed"
    assert len(result.run_events) == 3
    assert result.tool_call_count == 1


def test_result_payload_includes_trace_summary():
    response = AssistantMessage(text="pong", channel="cli", external_chat_id="smoke", session_id="cli:smoke")
    run_event = RunEvent(
        channel="cli",
        external_chat_id="smoke",
        session_id="cli:smoke",
        run_id="run-cli",
        event_type="run_finished",
        payload={"status": "completed"},
        created_at=1.0,
    )

    payload = result_payload(
        result=type(
            "Result",
            (),
            {
                "response": response,
                "error": "",
                "run_id": "run-cli",
                "run_status": "completed",
                "run_events": [run_event],
                "tool_call_count": 0,
            },
        )(),
        trace_summary={"event_count": 4, "part_count": 2, "file_change_count": 0},
    )

    assert payload["ok"] is True
    assert payload["session_id"] == "cli:smoke"
    assert payload["run_id"] == "run-cli"
    assert payload["trace"]["event_count"] == 4


def test_chat_command_outputs_json(monkeypatch):
    runner = CliRunner()

    async def fake_run_cli_chat(*args, **kwargs):
        response = AssistantMessage(text="pong", channel="cli", external_chat_id="default", session_id="cli:default")
        result = type(
            "Result",
            (),
            {
                "response": response,
                "error": "",
                "run_id": "run-cli",
                "run_status": "completed",
                "run_events": [],
                "tool_call_count": 0,
            },
        )()
        return result, {"event_count": 1, "part_count": 1, "file_change_count": 0}

    monkeypatch.setattr(commands.commands_chat, "run_cli_chat", fake_run_cli_chat)

    result = runner.invoke(commands.app, ["chat", "ping", "--json"])

    assert result.exit_code == 0
    assert '"reply": "pong"' in result.output
    assert '"session_id": "cli:default"' in result.output
