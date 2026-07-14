import asyncio

from aiohttp import web
import pytest
from typer.testing import CliRunner

from opensprite.bus import RunEvent
from opensprite.bus.dispatcher import MessageQueue
from opensprite.bus.message import (
    CLIENT_TURN_ID_METADATA_KEY,
    RESPONSE_KIND_METADATA_KEY,
    SESSION_COMMAND_RESPONSE_KIND,
    AssistantMessage,
)
from opensprite.channels.cli import CliAdapter
from opensprite.cli import commands
from opensprite.cli.commands_chat import (
    build_ws_url,
    _json_for_stdout,
    result_payload,
    run_web_chat,
    snapshot_workspace_for_session,
)
from opensprite.runs.events import TOOL_STARTED_EVENT
from opensprite.runs.lifecycle import RUN_CANCELLED_EVENT, RUN_FAILED_EVENT, RUN_FINISHED_EVENT, RUN_STARTED_EVENT


def test_build_ws_url_defaults_to_gateway_ws_path():
    assert build_ws_url("http://127.0.0.1:8765", external_chat_id="smoke") == (
        "ws://127.0.0.1:8765/ws?external_chat_id=smoke"
    )
    assert build_ws_url("https://example.test", access_token="secret") == "wss://example.test/ws?access_token=secret"


class FakeAgent:
    messages = None
    _message_bus = None

    async def reset_history(self, session_id):
        _ = session_id

    async def process(self, user_message):
        client_turn_id = user_message.metadata[CLIENT_TURN_ID_METADATA_KEY]
        await self._message_bus.publish_run_event(
            RunEvent(
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                run_id="run-cli",
                event_type=RUN_STARTED_EVENT,
                payload={"status": "running", CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                created_at=1.0,
            )
        )
        await self._message_bus.publish_run_event(
            RunEvent(
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                run_id="run-cli",
                event_type=TOOL_STARTED_EVENT,
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
                event_type=RUN_FINISHED_EVENT,
                payload={"status": "completed", CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                created_at=3.0,
            )
        )
        return AssistantMessage(
            text=f"echo:{user_message.text}",
            channel=user_message.channel,
            external_chat_id=user_message.external_chat_id,
            session_id=user_message.session_id,
            metadata={CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
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


def test_cli_adapter_waits_for_correlated_terminal_event_when_response_arrives_first():
    class ResponseFirstAgent:
        messages = None
        _message_bus = None

        async def process(self, user_message):
            client_turn_id = user_message.metadata[CLIENT_TURN_ID_METADATA_KEY]

            async def finish_later():
                await asyncio.sleep(0.01)
                await self._message_bus.publish_run_event(
                    RunEvent(
                        channel=user_message.channel,
                        external_chat_id=user_message.external_chat_id,
                        session_id=user_message.session_id,
                        run_id="run-response-first",
                        event_type=RUN_FINISHED_EVENT,
                        payload={
                            "status": "completed",
                            CLIENT_TURN_ID_METADATA_KEY: client_turn_id,
                        },
                    )
                )

            asyncio.create_task(finish_later())
            return AssistantMessage(
                text="response first",
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                metadata={CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
            )

    async def scenario():
        queue = MessageQueue(ResponseFirstAgent())
        processor = asyncio.create_task(queue.process_queue())
        adapter = CliAdapter(queue, external_chat_id="response-first")
        try:
            return await adapter.run_once("ping", timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

    result = asyncio.run(scenario())

    assert result.response.text == "response first"
    assert result.run_id == "run-response-first"
    assert result.run_status == "completed"


def test_cli_adapter_uses_configured_timeout_when_terminal_arrives_first():
    class TerminalFirstAgent:
        messages = None
        _message_bus = None

        async def process(self, user_message):
            client_turn_id = user_message.metadata[CLIENT_TURN_ID_METADATA_KEY]
            for event_type, status in (
                (RUN_STARTED_EVENT, "running"),
                (RUN_FINISHED_EVENT, "completed"),
            ):
                await self._message_bus.publish_run_event(
                    RunEvent(
                        channel=user_message.channel,
                        external_chat_id=user_message.external_chat_id,
                        session_id=user_message.session_id,
                        run_id="run-terminal-first",
                        event_type=event_type,
                        payload={
                            "status": status,
                            CLIENT_TURN_ID_METADATA_KEY: client_turn_id,
                        },
                    )
                )
            await asyncio.sleep(1.05)
            return AssistantMessage(
                text="delayed final response",
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                metadata={CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
            )

    async def scenario():
        queue = MessageQueue(TerminalFirstAgent())
        processor = asyncio.create_task(queue.process_queue())
        adapter = CliAdapter(queue, external_chat_id="terminal-first")
        try:
            return await adapter.run_once("ping", timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

    result = asyncio.run(scenario())

    assert result.response.text == "delayed final response"
    assert result.run_id == "run-terminal-first"
    assert result.run_status == "completed"


def test_cli_adapter_rejects_response_when_terminal_event_is_missing():
    class MissingTerminalAgent:
        messages = None
        _message_bus = None

        async def process(self, user_message):
            return AssistantMessage(
                text="response without terminal",
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
                metadata={
                    CLIENT_TURN_ID_METADATA_KEY: user_message.metadata[CLIENT_TURN_ID_METADATA_KEY]
                },
            )

    async def scenario():
        queue = MessageQueue(MissingTerminalAgent())
        processor = asyncio.create_task(queue.process_queue())
        adapter = CliAdapter(queue, external_chat_id="missing-terminal")
        try:
            with pytest.raises(TimeoutError, match="terminal state"):
                await adapter.run_once("ping", timeout=0.05)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "command",
    ["/help", "/stop", "/reset", "/cron help", "/curator status"],
)
def test_cli_adapter_accepts_correlated_session_command_without_run(command):
    async def scenario():
        queue = MessageQueue(FakeAgent())
        processor = asyncio.create_task(queue.process_queue())
        adapter = CliAdapter(queue, external_chat_id="command")
        try:
            return await adapter.run_once(command, timeout=2)
        finally:
            await queue.stop()
            await asyncio.wait_for(processor, timeout=2)

    result = asyncio.run(scenario())

    assert result.response.text
    assert result.response.metadata[RESPONSE_KIND_METADATA_KEY] == SESSION_COMMAND_RESPONSE_KIND
    assert result.response.metadata[CLIENT_TURN_ID_METADATA_KEY].startswith("turn_")
    assert result.run_id is None
    assert result.run_status == ""
    assert result.run_events == []
    assert result_payload(result, {})["ok"] is True


def test_cli_adapter_ignores_other_session_and_run_events():
    async def scenario():
        adapter = CliAdapter(object(), external_chat_id="target")
        foreign_response = AssistantMessage(
            text="wrong reply",
            channel="cli",
            external_chat_id="other",
            session_id="cli:other",
        )
        foreign_completed = RunEvent(
            channel="cli",
            external_chat_id="other",
            session_id="cli:other",
            run_id="run-other",
            event_type=RUN_FINISHED_EVENT,
            payload={"status": "completed"},
            created_at=1.0,
        )
        current_started = RunEvent(
            channel="cli",
            external_chat_id="target",
            session_id="cli:target",
            run_id="run-target",
            event_type=RUN_STARTED_EVENT,
            payload={"status": "running"},
            created_at=2.0,
        )
        other_run_completed = RunEvent(
            channel="cli",
            external_chat_id="target",
            session_id="cli:target",
            run_id="run-other-in-session",
            event_type=RUN_FINISHED_EVENT,
            payload={"status": "completed"},
            created_at=3.0,
        )

        await adapter._on_run_event(foreign_completed)
        await adapter._on_response(foreign_response, "cli", "other")
        assert adapter._run_id is None
        assert adapter._run_status == ""
        assert adapter._response is None

        await adapter._on_run_event(current_started)
        await adapter._on_run_event(other_run_completed)
        assert adapter._run_id == "run-target"
        assert adapter._run_status == ""

    asyncio.run(scenario())


def test_cli_adapter_ignores_foreign_turn_in_same_session():
    async def scenario():
        adapter = CliAdapter(object(), external_chat_id="target")
        adapter._client_turn_id = "turn-current"
        foreign_started = RunEvent(
            channel="cli",
            external_chat_id="target",
            session_id="cli:target",
            run_id="run-foreign",
            event_type=RUN_STARTED_EVENT,
            payload={"status": "running", CLIENT_TURN_ID_METADATA_KEY: "turn-foreign"},
        )
        current_started = RunEvent(
            channel="cli",
            external_chat_id="target",
            session_id="cli:target",
            run_id="run-current",
            event_type=RUN_STARTED_EVENT,
            payload={"status": "running", CLIENT_TURN_ID_METADATA_KEY: "turn-current"},
        )
        current_finished = RunEvent(
            channel="cli",
            external_chat_id="target",
            session_id="cli:target",
            run_id="run-current",
            event_type=RUN_FINISHED_EVENT,
            payload={"status": "completed", CLIENT_TURN_ID_METADATA_KEY: "turn-current"},
        )
        foreign_response = AssistantMessage(
            text="foreign",
            channel="cli",
            external_chat_id="target",
            session_id="cli:target",
            metadata={CLIENT_TURN_ID_METADATA_KEY: "turn-foreign"},
        )
        current_response = AssistantMessage(
            text="current",
            channel="cli",
            external_chat_id="target",
            session_id="cli:target",
            metadata={CLIENT_TURN_ID_METADATA_KEY: "turn-current"},
        )

        await adapter._on_run_event(foreign_started)
        await adapter._on_response(foreign_response, "cli", "target")
        await adapter._on_run_event(current_started)
        await adapter._on_run_event(current_finished)
        await adapter._on_response(current_response, "cli", "target")
        return adapter

    adapter = asyncio.run(scenario())

    assert adapter._run_id == "run-current"
    assert adapter._run_status == "completed"
    assert adapter._response is not None
    assert adapter._response.text == "current"


def test_result_payload_includes_trace_summary():
    response = AssistantMessage(text="pong", channel="cli", external_chat_id="smoke", session_id="cli:smoke")
    run_event = RunEvent(
        channel="cli",
        external_chat_id="smoke",
        session_id="cli:smoke",
        run_id="run-cli",
        event_type=RUN_FINISHED_EVENT,
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


@pytest.mark.parametrize("run_status", ["", "running", "stopped", "failed"])
def test_result_payload_requires_completed_run_status(run_status):
    response = AssistantMessage(text="pong", channel="cli", external_chat_id="smoke", session_id="cli:smoke")

    payload = result_payload(
        result=type(
            "Result",
            (),
            {
                "response": response,
                "error": "",
                "run_id": "run-cli",
                "run_status": run_status,
                "run_events": [],
                "tool_call_count": 0,
            },
        )(),
        trace_summary={},
    )

    assert payload["ok"] is False


def test_json_for_stdout_escapes_non_ascii_for_windows_codepage_encoding():
    rendered = _json_for_stdout({"reply": "✅ 繁體中文"}, encoding="cp950")

    assert "\\u2705" in rendered
    assert "\\u7e41" in rendered
    rendered.encode("cp950")


def test_json_for_stdout_preserves_unicode_for_utf8():
    rendered = _json_for_stdout({"reply": "✅ 繁體中文"}, encoding="utf-8")

    assert "✅ 繁體中文" in rendered


def test_snapshot_workspace_for_session_copies_repo_under_session_workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("repo instructions", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("secret-ish", encoding="utf-8")
    (source / "frontend").mkdir()
    (source / "frontend" / "package.json").write_text("{}", encoding="utf-8")
    (source / "frontend" / "node_modules").mkdir()
    (source / "frontend" / "node_modules" / "leftpad.js").write_text("", encoding="utf-8")
    (source / "tmp").mkdir()
    (source / "tmp" / "screenshot.png").write_text("", encoding="utf-8")
    config_path = tmp_path / "app-home" / "opensprite.json"

    metadata = snapshot_workspace_for_session(source, session_id="web:smoke", config_path=config_path)

    assert metadata is not None
    snapshot_root = tmp_path / "app-home" / "workspace" / "sessions" / "web" / "smoke" / "repo"
    assert snapshot_root.joinpath("AGENTS.md").read_text(encoding="utf-8") == "repo instructions"
    assert snapshot_root.joinpath("frontend", "package.json").exists()
    assert not snapshot_root.joinpath(".git").exists()
    assert not snapshot_root.joinpath("frontend", "node_modules").exists()
    assert not snapshot_root.joinpath("tmp").exists()
    assert metadata["path"] == "repo"
    assert metadata["files"] == 2


def test_run_web_chat_sends_message_to_gateway_websocket(tmp_path):
    async def scenario():
        seen_messages = []
        source = tmp_path / "source"
        source.mkdir()
        (source / "README.md").write_text("hello", encoding="utf-8")
        config_path = tmp_path / "app-home" / "opensprite.json"

        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            seen_messages.append(message)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-web",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-web",
                    "event_type": RUN_FINISHED_EVENT,
                    "status": "completed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "completed"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "echo:" + message["text"],
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            payload = await run_web_chat(
                "ping",
                gateway_url=f"http://127.0.0.1:{port}",
                external_chat_id="web-smoke",
                config_path=config_path,
                workspace_snapshot=source,
            )
        finally:
            await runner.cleanup()
        return payload, seen_messages

    payload, seen_messages = asyncio.run(scenario())

    assert seen_messages[0]["text"] == "ping"
    assert seen_messages[0]["session_id"] == "web:web-smoke"
    assert seen_messages[0]["metadata"]["gateway_url"].startswith("http://127.0.0.1:")
    assert seen_messages[0]["metadata"]["ws_url"].startswith("ws://127.0.0.1:")
    assert seen_messages[0]["metadata"][CLIENT_TURN_ID_METADATA_KEY].startswith("turn_")
    assert seen_messages[0]["metadata"]["workspace_snapshot"]["path"] == "repo"
    assert (tmp_path / "app-home" / "workspace" / "sessions" / "web" / "web-smoke" / "repo" / "README.md").exists()
    assert payload["mode"] == "web"
    assert payload["workspace_snapshot"]["files"] == 1
    assert payload["reply"] == "echo:ping"
    assert payload["run_id"] == "run-web"
    assert payload["run_status"] == "completed"


@pytest.mark.parametrize(
    "command",
    ["/help", "/stop", "/reset", "/cron help", "/curator status"],
)
def test_run_web_chat_accepts_only_correlated_session_command_response(command):
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json(
                {
                    "type": "session",
                    "external_chat_id": external_chat_id,
                    "session_id": session_id,
                }
            )
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            command_metadata = {
                RESPONSE_KIND_METADATA_KEY: SESSION_COMMAND_RESPONSE_KIND,
            }
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "foreign command response",
                    "metadata": {
                        **command_metadata,
                        CLIENT_TURN_ID_METADATA_KEY: "turn_foreign",
                    },
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": f"command:{message['text']}",
                    "metadata": {
                        **command_metadata,
                        CLIENT_TURN_ID_METADATA_KEY: client_turn_id,
                    },
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat(
                command,
                gateway_url=f"http://127.0.0.1:{port}",
                external_chat_id="web-command",
                timeout_seconds=2,
            )
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is True
    assert payload["reply"] == f"command:{command}"
    assert payload["run_id"] is None
    assert payload["run_status"] == ""
    assert payload["run_event_count"] == 0


def test_run_web_chat_ignores_uncorrelated_cancelled_run_before_command_ack():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json(
                {
                    "type": "session",
                    "external_chat_id": external_chat_id,
                    "session_id": session_id,
                }
            )
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-being-stopped",
                    "event_type": RUN_CANCELLED_EVENT,
                    "status": "cancelled",
                    "payload": {"status": "cancelled"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "stop acknowledged",
                    "metadata": {
                        RESPONSE_KIND_METADATA_KEY: SESSION_COMMAND_RESPONSE_KIND,
                        CLIENT_TURN_ID_METADATA_KEY: client_turn_id,
                    },
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat(
                "/stop",
                gateway_url=f"http://127.0.0.1:{port}",
                external_chat_id="web-stop",
                timeout_seconds=2,
            )
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is True
    assert payload["reply"] == "stop acknowledged"
    assert payload["run_id"] is None
    assert payload["run_status"] == ""
    assert payload["run_event_count"] == 0


def test_run_web_chat_ignores_stale_run_events_before_current_run_start():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-old",
                    "event_type": RUN_FINISHED_EVENT,
                    "status": "completed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: "turn-queued-a", "status": "completed"},
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-new",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "unrelated same-session notification",
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-new",
                    "event_type": RUN_FINISHED_EVENT,
                    "status": "completed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "completed"},
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "completed"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "echo:" + message["text"],
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat("ping", gateway_url=f"http://127.0.0.1:{port}", external_chat_id="web-smoke")
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["reply"] == "echo:ping"
    assert payload["run_id"] == "run-new"
    assert payload["run_status"] == "completed"
    assert payload["run_event_count"] == 2
    assert {event["run_id"] for event in payload["recent_events"]} == {"run-new"}


def test_run_web_chat_ignores_unrelated_messages_before_current_run_start():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "unrelated cron reminder reply",
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-new",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "echo:" + message["text"],
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-new",
                    "event_type": RUN_FINISHED_EVENT,
                    "status": "completed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "completed"},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat("ping", gateway_url=f"http://127.0.0.1:{port}", external_chat_id="web-smoke")
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["reply"] == "echo:ping"
    assert payload["run_id"] == "run-new"
    assert payload["run_status"] == "completed"
    assert payload["run_event_count"] == 2


def test_run_web_chat_ignores_intermediate_messages_until_run_finishes():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-web",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "正在讀取技能〈memory〉…",
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-web",
                    "event_type": RUN_FINISHED_EVENT,
                    "status": "completed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "completed"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "final:" + message["text"],
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat("ping", gateway_url=f"http://127.0.0.1:{port}", external_chat_id="web-smoke")
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["reply"] == "final:ping"
    assert payload["run_status"] == "completed"
    assert payload["run_event_count"] == 2


def test_run_web_chat_returns_when_final_message_arrives_before_run_finished():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-web",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "final:" + message["text"],
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-web",
                    "event_type": RUN_FINISHED_EVENT,
                    "status": "completed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "completed"},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat("ping", gateway_url=f"http://127.0.0.1:{port}", external_chat_id="web-smoke")
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is True
    assert payload["reply"] == "final:ping"
    assert payload["run_status"] == "completed"
    assert payload["run_event_count"] == 2


def test_run_web_chat_uses_configured_timeout_when_terminal_arrives_first():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json(
                {
                    "type": "session",
                    "external_chat_id": external_chat_id,
                    "session_id": session_id,
                }
            )
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            for event_type, status in (
                (RUN_STARTED_EVENT, "running"),
                (RUN_FINISHED_EVENT, "completed"),
            ):
                await ws.send_json(
                    {
                        "type": "run_event",
                        "session_id": session_id,
                        "external_chat_id": external_chat_id,
                        "run_id": "run-terminal-first",
                        "event_type": event_type,
                        "status": status,
                        "payload": {
                            "status": status,
                            CLIENT_TURN_ID_METADATA_KEY: client_turn_id,
                        },
                    }
                )
            await asyncio.sleep(1.05)
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "delayed final response",
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat(
                "ping",
                gateway_url=f"http://127.0.0.1:{port}",
                external_chat_id="web-terminal-first",
                timeout_seconds=2,
            )
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is True
    assert payload["reply"] == "delayed final response"
    assert payload["run_id"] == "run-terminal-first"
    assert payload["run_status"] == "completed"


def test_run_web_chat_rejects_reply_when_terminal_event_is_missing_before_timeout():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-web",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "final:" + message["text"],
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await asyncio.sleep(0.25)
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat(
                "ping",
                gateway_url=f"http://127.0.0.1:{port}",
                external_chat_id="web-smoke",
                timeout_seconds=0.1,
            )
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is False
    assert payload["reply"] == "final:ping"
    assert payload["run_id"] == "run-web"
    assert payload["run_status"] == ""
    assert payload["error_type"] == "TimeoutError"


def test_run_web_chat_returns_trace_ids_when_gateway_fails_after_run_start():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-failed",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-failed",
                    "event_type": RUN_FAILED_EVENT,
                    "status": "failed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "failed"},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat("ping", gateway_url=f"http://127.0.0.1:{port}", external_chat_id="web-smoke")
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is False
    assert payload["session_id"] == "web:web-smoke"
    assert payload["run_id"] == "run-failed"
    assert payload["run_status"] == "failed"
    assert payload["run_event_count"] == 2
    assert payload["error_type"] == "RuntimeError"


@pytest.mark.parametrize("terminal_status", ["", "running", "stopped", "needs_verification"])
def test_run_web_chat_marks_non_completed_terminal_status_not_ok(terminal_status):
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-verify",
                    "event_type": RUN_STARTED_EVENT,
                    "status": "running",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "running"},
                }
            )
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-verify",
                    "event_type": RUN_FINISHED_EVENT,
                    "status": terminal_status,
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": terminal_status},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "needs check:" + message["text"],
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat("ping", gateway_url=f"http://127.0.0.1:{port}", external_chat_id="web-smoke")
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is False
    assert payload["run_id"] == "run-verify"
    assert payload["run_status"] == terminal_status
    assert payload["error_type"] == "RunStatusError"


def test_run_web_chat_marks_run_failed_status_not_ok_even_with_apology_message():
    async def scenario():
        async def handle_ws(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            external_chat_id = request.query.get("external_chat_id") or "default"
            session_id = f"web:{external_chat_id}"
            await ws.send_json({"type": "session", "external_chat_id": external_chat_id, "session_id": session_id})
            message = await ws.receive_json(timeout=2)
            client_turn_id = message["metadata"][CLIENT_TURN_ID_METADATA_KEY]
            await ws.send_json(
                {
                    "type": "run_event",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "run_id": "run-failed",
                    "event_type": RUN_FAILED_EVENT,
                    "status": "failed",
                    "payload": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id, "status": "failed"},
                }
            )
            await ws.send_json(
                {
                    "type": "message",
                    "session_id": session_id,
                    "external_chat_id": external_chat_id,
                    "text": "抱歉，處理您的訊息時發生錯誤: ",
                    "metadata": {CLIENT_TURN_ID_METADATA_KEY: client_turn_id},
                }
            )
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/ws", handle_ws)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = getattr(site, "_server").sockets[0].getsockname()[1]
        try:
            return await run_web_chat("ping", gateway_url=f"http://127.0.0.1:{port}", external_chat_id="web-smoke")
        finally:
            await runner.cleanup()

    payload = asyncio.run(scenario())

    assert payload["ok"] is False
    assert payload["run_id"] == "run-failed"
    assert payload["run_status"] == "failed"
    assert payload["error_type"] == "RunStatusError"


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


def test_chat_command_exits_nonzero_when_local_run_did_not_complete(monkeypatch):
    runner = CliRunner()

    async def fake_run_cli_chat(*args, **kwargs):
        response = AssistantMessage(text="partial", channel="cli", external_chat_id="default", session_id="cli:default")
        result = type(
            "Result",
            (),
            {
                "response": response,
                "error": "",
                "run_id": "run-cli",
                "run_status": "stopped",
                "run_events": [],
                "tool_call_count": 0,
            },
        )()
        return result, {"event_count": 1, "part_count": 1, "file_change_count": 0}

    monkeypatch.setattr(commands.commands_chat, "run_cli_chat", fake_run_cli_chat)

    result = runner.invoke(commands.app, ["chat", "ping", "--json"])

    assert result.exit_code == 1
    assert '"ok": false' in result.output
    assert '"run_status": "stopped"' in result.output


def test_chat_command_via_web_outputs_json(monkeypatch):
    runner = CliRunner()

    async def fake_run_web_chat(*args, **kwargs):
        return {
            "ok": True,
            "mode": "web",
            "session_id": "web:cli-smoke",
            "external_chat_id": "cli-smoke",
            "run_id": "run-web",
            "run_status": "completed",
            "reply": "web-pong",
            "run_event_count": 2,
            "tool_call_count": 0,
            "elapsed_seconds": 0.1,
            "recent_events": [],
        }

    monkeypatch.setattr(commands.commands_chat, "run_web_chat", fake_run_web_chat)

    result = runner.invoke(commands.app, ["chat", "ping", "--via-web", "--json"])

    assert result.exit_code == 0
    assert '"mode": "web"' in result.output
    assert '"reply": "web-pong"' in result.output


def test_chat_command_via_web_outputs_failure_json(monkeypatch):
    runner = CliRunner()

    async def fake_run_web_chat(*args, **kwargs):
        return {
            "ok": False,
            "mode": "web",
            "session_id": "web:cli-smoke",
            "external_chat_id": "cli-smoke",
            "run_id": "run-failed",
            "run_status": "failed",
            "reply": "",
            "run_event_count": 2,
            "tool_call_count": 0,
            "elapsed_seconds": 0.1,
            "recent_events": [],
            "error": "Web gateway chat failed: boom",
            "error_type": "RuntimeError",
        }

    monkeypatch.setattr(commands.commands_chat, "run_web_chat", fake_run_web_chat)

    result = runner.invoke(commands.app, ["chat", "ping", "--via-web", "--json"])

    assert result.exit_code == 1
    assert '"ok": false' in result.output
    assert '"run_id": "run-failed"' in result.output
    assert '"error_type": "RuntimeError"' in result.output
