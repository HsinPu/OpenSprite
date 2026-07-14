"""Run event helpers for one prepared user turn."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from .turn_input import PreparedTurnInput


class TurnEventEmitter:
    def __init__(self, emit_run_event: Callable[..., Awaitable[None]]) -> None:
        self._emit_run_event = emit_run_event

    async def emit(
        self,
        turn: PreparedTurnInput,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await self._emit_run_event(
            turn.session_id,
            run_id,
            event_type,
            payload,
            channel=turn.channel,
            external_chat_id=turn.external_chat_id,
        )
