import asyncio

from opensprite.agent.background_session_notifications import BackgroundSessionNotificationService
from opensprite.tools.process_runtime import BackgroundSession
from opensprite.tools.shell_runtime import CapturedOutputChunk


class _FakeProcess:
    pid = 1234


class _Bus:
    def __init__(self):
        self.messages = []

    async def publish_inbound(self, message):
        self.messages.append(message)


async def _save_message(*args, **kwargs):
    pass


def _session() -> BackgroundSession:
    return BackgroundSession(
        session_id="bg-1",
        command="npm test",
        cwd=None,
        process=_FakeProcess(),
        read_tasks=[],
        output_chunks=[
            CapturedOutputChunk(stream_name="stdout", data=b"ok\n"),
            CapturedOutputChunk(stream_name="stderr", data=b"warn\n"),
        ],
        timeout_seconds=None,
        drain_timeout=1.0,
        started_at=10.0,
        finished_at=12.5,
        termination_reason="exit",
        exit_code=0,
    )


def test_background_session_summary_request_includes_process_result():
    text = BackgroundSessionNotificationService.format_summary_request(_session())

    assert "Session ID: bg-1" in text
    assert "Command: npm test" in text
    assert "Termination: exit" in text
    assert "Exit code: 0" in text
    assert "Runtime: 2.50s" in text
    assert "ok" in text
    assert "[stderr] warn" in text


def test_background_session_exit_notifier_publishes_summary_request():
    bus = _Bus()
    service = BackgroundSessionNotificationService(
        message_bus_getter=lambda: bus,
        save_message=_save_message,
    )
    notifier = service.make_exit_notifier(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
    )

    assert notifier is not None
    asyncio.run(notifier(_session()))

    assert len(bus.messages) == 1
    message = bus.messages[0]
    assert message.channel == "web"
    assert message.sender_id == "system:background"
    assert message.sender_name == "background process"
    assert message.external_chat_id == "browser-1"
    assert message.session_id == "web:browser-1"
    assert "Command: npm test" in message.content
    assert message.metadata == {
        "channel": "web",
        "external_chat_id": "browser-1",
        "kind": "background_session_summary_request",
        "session_id": "bg-1",
        "termination_reason": "exit",
        "exit_code": 0,
        "_bypass_commands": True,
    }
