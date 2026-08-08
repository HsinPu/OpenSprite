from datetime import datetime

from opensprite.core.contracts.bus_events import (
    InboundMessage,
    OutboundMessage,
    RunEvent,
    SessionStatusEvent,
)


def test_inbound_message_uses_explicit_or_transport_session_key():
    explicit = InboundMessage(
        channel="telegram",
        sender_id="user-1",
        external_chat_id="chat-1",
        content="hello",
        session_id="session-1",
    )
    fallback = InboundMessage(
        channel="web",
        sender_id="user-2",
        external_chat_id="chat-2",
        content="hello",
    )

    assert explicit.session_key == "session-1"
    assert fallback.session_key == "web:chat-2"
    assert isinstance(fallback.timestamp, datetime)


def test_bus_event_mutable_defaults_are_isolated():
    inbound_a = InboundMessage("web", "user-1", "chat-1", "hello")
    inbound_b = InboundMessage("web", "user-2", "chat-2", "hello")
    outbound_a = OutboundMessage("web", "chat-1", "hello")
    outbound_b = OutboundMessage("web", "chat-2", "hello")
    run_a = RunEvent("web", "chat-1", "session-1", "run-1", "started")
    run_b = RunEvent("web", "chat-2", "session-2", "run-2", "started")
    status_a = SessionStatusEvent("session-1", "running")
    status_b = SessionStatusEvent("session-2", "idle")

    assert inbound_a.images is not inbound_b.images
    assert inbound_a.audios is not inbound_b.audios
    assert inbound_a.videos is not inbound_b.videos
    assert inbound_a.metadata is not inbound_b.metadata
    assert outbound_a.images is not outbound_b.images
    assert outbound_a.metadata is not outbound_b.metadata
    assert run_a.payload is not run_b.payload
    assert status_a.metadata is not status_b.metadata
    assert isinstance(run_a.created_at, float)
    assert isinstance(status_a.updated_at, float)
