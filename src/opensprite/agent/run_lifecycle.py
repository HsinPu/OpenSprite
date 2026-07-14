"""Fixed run lifecycle helpers for one user turn."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol
from uuid import uuid4

from ..bus.message import CLIENT_TURN_ID_METADATA_KEY, UserMessage
from ..runs.events import INBOUND_MEDIA_EVENT_PREFIX, INBOUND_MEDIA_PERSISTED_EVENT
from ..runs.trace import AgentRunStateService, RunTraceRecorder


class PreparedTurnLifecycleInput(Protocol):
    """Prepared turn fields needed by run lifecycle bookkeeping."""

    session_id: str
    channel: str | None
    external_chat_id: str | None
    media_events: list[dict[str, Any]]


@dataclass(frozen=True)
class ActiveTurnRun:
    """Identifiers for one active user-turn run."""

    session_id: str
    run_id: str
    channel: str | None
    external_chat_id: str | None
    client_turn_id: str | None = None


class RunLifecycleService:
    """Own fixed run start, failure, media-event, and finish bookkeeping."""

    def __init__(
        self,
        *,
        run_trace: RunTraceRecorder,
        run_state: AgentRunStateService,
        emit_run_event: Callable[..., Awaitable[None]],
        clear_delegated_task_updates: Callable[[str], None],
        clear_workflow_outcomes: Callable[[str], None],
        format_log_preview: Callable[..., str],
    ):
        self.run_trace = run_trace
        self.run_state = run_state
        self._emit_run_event = emit_run_event
        self._clear_delegated_task_updates = clear_delegated_task_updates
        self._clear_workflow_outcomes = clear_workflow_outcomes
        self._format_log_preview = format_log_preview

    async def start_turn(
        self,
        *,
        user_message: UserMessage,
        turn: PreparedTurnLifecycleInput,
    ) -> ActiveTurnRun:
        """Create the run id, mark the session active, and start trace recording."""
        run_id = f"run_{uuid4().hex}"
        client_turn_id = str(
            (user_message.metadata or {}).get(CLIENT_TURN_ID_METADATA_KEY) or ""
        ).strip() or None
        run = ActiveTurnRun(
            session_id=turn.session_id,
            run_id=run_id,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
            client_turn_id=client_turn_id,
        )
        self.run_state.start(turn.session_id, run_id)
        try:
            await self.run_trace.start_turn_run(
                turn.session_id,
                run_id,
                channel=turn.channel,
                external_chat_id=turn.external_chat_id,
                sender_id=user_message.sender_id,
                sender_name=user_message.sender_name,
                text=user_message.text,
                images=user_message.images,
                audios=user_message.audios,
                videos=user_message.videos,
                client_turn_id=client_turn_id,
            )
        except BaseException as exc:
            # Cancellation and trace-start failures happen before AgentTurnRunner's
            # outer try/finally. Best-effort close a run that may already have been
            # created, then release the reservation so the session does not remain
            # permanently busy. Never mask the original start failure.
            status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
            event_payload = {
                "status": status,
                "error": "cancelled"
                if isinstance(exc, asyncio.CancelledError)
                else self._format_log_preview(f"{type(exc).__name__}: {exc}", max_chars=240),
            }
            if client_turn_id:
                event_payload[CLIENT_TURN_ID_METADATA_KEY] = client_turn_id
            try:
                await self.run_trace.fail_run(
                    turn.session_id,
                    run_id,
                    status=status,
                    event_payload=event_payload,
                    channel=turn.channel,
                    external_chat_id=turn.external_chat_id,
                )
            except BaseException:
                pass
            self.finish_turn(run)
            raise
        return run

    async def record_inbound_media(self, *, run: ActiveTurnRun, turn: PreparedTurnLifecycleInput) -> None:
        """Record inbound media persistence events for this run."""
        for media_event in turn.media_events:
            await self._emit_run_event(
                run.session_id,
                run.run_id,
                INBOUND_MEDIA_PERSISTED_EVENT
                if media_event.get("status") == "persisted"
                else f"{INBOUND_MEDIA_EVENT_PREFIX}{media_event.get('status') or 'unknown'}",
                {"schema_version": 1, **dict(media_event)},
                channel=run.channel,
                external_chat_id=run.external_chat_id,
            )

    async def record_cancelled(self, run: ActiveTurnRun) -> None:
        """Record cooperative cancellation for this run."""
        event_payload = {"status": "cancelled", "error": "cancelled"}
        if run.client_turn_id:
            event_payload[CLIENT_TURN_ID_METADATA_KEY] = run.client_turn_id
        await self.run_trace.fail_run(
            run.session_id,
            run.run_id,
            status="cancelled",
            event_payload=event_payload,
            channel=run.channel,
            external_chat_id=run.external_chat_id,
        )

    async def record_failed(self, run: ActiveTurnRun, exc: Exception) -> None:
        """Record an unexpected failure for this run."""
        event_payload = {
            "status": "failed",
            "error": self._format_log_preview(f"{type(exc).__name__}: {exc}", max_chars=240),
        }
        if run.client_turn_id:
            event_payload[CLIENT_TURN_ID_METADATA_KEY] = run.client_turn_id
        await self.run_trace.fail_run(
            run.session_id,
            run.run_id,
            status="failed",
            event_payload=event_payload,
            channel=run.channel,
            external_chat_id=run.external_chat_id,
        )

    def finish_turn(self, run: ActiveTurnRun) -> None:
        """Clear per-run transient state and mark the session inactive."""
        self._clear_delegated_task_updates(run.run_id)
        self._clear_workflow_outcomes(run.run_id)
        self.run_state.finish(run.session_id, run.run_id)
