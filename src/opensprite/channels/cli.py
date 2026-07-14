"""One-shot CLI channel adapter for local chat smoke tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..bus import RunEvent, SessionStatusEvent
from ..bus.message import (
    CLIENT_TURN_ID_METADATA_KEY,
    RESPONSE_KIND_METADATA_KEY,
    SESSION_COMMAND_RESPONSE_KIND,
    AssistantMessage,
    MessageAdapter,
    UserMessage,
)
from ..runs.events import TOOL_STARTED_EVENT
from ..runs.lifecycle import TERMINAL_RUN_EVENTS
from .identity import build_session_id, normalize_identifier


@dataclass
class CliChatResult:
    """Result returned by a one-shot CLI chat turn."""

    response: AssistantMessage
    run_id: str | None = None
    run_status: str = ""
    run_events: list[RunEvent] = field(default_factory=list)
    statuses: list[SessionStatusEvent] = field(default_factory=list)
    error: str = ""

    @property
    def tool_call_count(self) -> int:
        return sum(1 for event in self.run_events if event.event_type == TOOL_STARTED_EVENT)


class CliAdapter(MessageAdapter):
    """Small one-shot channel adapter used by `opensprite chat`."""

    def __init__(
        self,
        mq: Any,
        *,
        channel_instance_id: str = "cli",
        external_chat_id: str = "default",
        session_id: str | None = None,
        sender_id: str = "cli-user",
        sender_name: str = "OpenSprite CLI",
    ):
        self.mq = mq
        self.channel_type = "cli"
        self.channel_instance_id = normalize_identifier(channel_instance_id, fallback="cli")
        self.external_chat_id = str(external_chat_id or "default").strip() or "default"
        self.session_id = session_id or build_session_id(self.channel_instance_id, self.external_chat_id)
        self.sender_id = sender_id
        self.sender_name = sender_name
        self._response: AssistantMessage | None = None
        self._response_event = asyncio.Event()
        self._terminal_event = asyncio.Event()
        self._run_id: str | None = None
        self._run_status = ""
        self._run_events: list[RunEvent] = []
        self._statuses: list[SessionStatusEvent] = []
        self._error = ""
        self._client_turn_id: str | None = None

    async def to_user_message(self, raw_message: Any) -> UserMessage:
        payload = dict(raw_message) if isinstance(raw_message, dict) else {"text": str(raw_message or "")}
        return UserMessage(
            text=str(payload.get("text") or ""),
            channel=self.channel_instance_id,
            external_chat_id=str(payload.get("external_chat_id") or self.external_chat_id),
            session_id=str(payload.get("session_id") or self.session_id),
            sender_id=str(payload.get("sender_id") or self.sender_id),
            sender_name=str(payload.get("sender_name") or self.sender_name),
            metadata=dict(payload.get("metadata") or {}),
            raw=payload,
        )

    async def send(self, message: AssistantMessage) -> None:
        self._response = message
        self._response_event.set()

    async def _on_response(self, message: AssistantMessage, channel: str, external_chat_id: str | None) -> None:
        _ = channel
        if str(message.session_id or "") != self.session_id:
            return
        if external_chat_id and str(external_chat_id) != self.external_chat_id:
            return
        if self._client_turn_id is not None:
            response_turn_id = str(
                (message.metadata or {}).get(CLIENT_TURN_ID_METADATA_KEY) or ""
            ).strip()
            if response_turn_id != self._client_turn_id:
                return
        await self.send(message)

    async def _on_run_event(self, event: RunEvent) -> None:
        if str(event.session_id or "") != self.session_id:
            return
        event_run_id = str(event.run_id or "").strip()
        if not event_run_id:
            return
        if self._client_turn_id is not None:
            event_turn_id = str(
                (event.payload or {}).get(CLIENT_TURN_ID_METADATA_KEY) or ""
            ).strip()
            if event_turn_id and event_turn_id != self._client_turn_id:
                return
            if self._run_id is None and event_turn_id != self._client_turn_id:
                return
        if self._run_id is not None and event_run_id != self._run_id:
            return
        self._run_events.append(event)
        if self._run_id is None:
            self._run_id = event_run_id
        if event.event_type in TERMINAL_RUN_EVENTS:
            status = ""
            if not status and isinstance(event.payload, dict):
                status = str(event.payload.get("status") or "")
            self._run_status = status or event.event_type
            self._terminal_event.set()

    async def _on_session_status(self, event: SessionStatusEvent) -> None:
        if str(event.session_id or "") != self.session_id:
            return
        self._statuses.append(event)

    async def _on_error(self, session_id: str, error: str) -> None:
        if str(session_id or "") != self.session_id:
            return
        self._error = error
        self._response_event.set()

    def _has_session_command_response(self) -> bool:
        return self._response is not None and (
            (self._response.metadata or {}).get(RESPONSE_KIND_METADATA_KEY)
            == SESSION_COMMAND_RESPONSE_KIND
        )

    def register(self) -> None:
        self.mq.register_response_handler(self.channel_instance_id, self._on_response)
        self.mq.register_run_event_handler(self.channel_instance_id, self._on_run_event)
        self.mq.register_session_status_handler(self.channel_instance_id, self._on_session_status)
        self.mq.register_error_handler(self.channel_instance_id, self._on_error)

    def unregister(self) -> None:
        self.mq.unregister_response_handler(self.channel_instance_id)
        self.mq.unregister_run_event_handler(self.channel_instance_id)
        self.mq.unregister_session_status_handler(self.channel_instance_id)
        self.mq.unregister_error_handler(self.channel_instance_id)

    async def run_once(self, text: str, *, timeout: float = 120.0, metadata: dict[str, Any] | None = None) -> CliChatResult:
        """Send one CLI message through the queue and wait for the assistant response."""
        self._response = None
        self._response_event.clear()
        self._terminal_event.clear()
        self._run_id = None
        self._run_status = ""
        self._run_events.clear()
        self._statuses.clear()
        self._error = ""
        self._client_turn_id = f"turn_{uuid4().hex}"
        self.register()
        try:
            user_message = await self.to_user_message(
                {
                    "text": text,
                    "external_chat_id": self.external_chat_id,
                    "session_id": self.session_id,
                    "sender_id": self.sender_id,
                    "sender_name": self.sender_name,
                    "metadata": {
                        "source": "cli",
                        **dict(metadata or {}),
                        CLIENT_TURN_ID_METADATA_KEY: self._client_turn_id,
                    },
                }
            )
            await self.mq.enqueue(user_message)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while self._response is None or (
                not self._terminal_event.is_set() and not self._has_session_command_response()
            ):
                if self._error:
                    raise RuntimeError(self._error)
                now = loop.time()
                remaining = deadline - now
                if remaining <= 0:
                    if self._terminal_event.is_set():
                        raise RuntimeError("CLI chat run ended without an assistant response")
                    raise TimeoutError(f"Timed out waiting for CLI chat terminal state after {timeout:g}s")

                waiters = []
                if self._response is None:
                    waiters.append(asyncio.create_task(self._response_event.wait()))
                if not self._terminal_event.is_set():
                    waiters.append(asyncio.create_task(self._terminal_event.wait()))
                try:
                    done, pending = await asyncio.wait(
                        waiters,
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                except BaseException:
                    for waiter in waiters:
                        waiter.cancel()
                    await asyncio.gather(*waiters, return_exceptions=True)
                    raise
                for waiter in pending:
                    waiter.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                if not done:
                    continue
            if self._response is None:
                raise RuntimeError(self._error or "CLI chat did not receive an assistant response")
            return CliChatResult(
                response=self._response,
                run_id=self._run_id,
                run_status=self._run_status,
                run_events=list(self._run_events),
                statuses=list(self._statuses),
                error=self._error,
            )
        finally:
            self.unregister()
