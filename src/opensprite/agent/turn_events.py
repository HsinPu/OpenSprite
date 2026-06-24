"""Run event helpers for one prepared user turn."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from .completion_gate import CompletionGateResult
from .turn_input import PreparedTurnInput
from .turn_outcome import (
    TURN_METADATA_COMPLETION_REASON_FIELD,
    TURN_METADATA_COMPLETION_STATUS_FIELD,
)


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

    async def emit_auto_continue(
        self,
        *,
        turn: PreparedTurnInput,
        run_id: str,
        event_type: str,
        decision: Any,
        completion_result: CompletionGateResult,
    ) -> None:
        await self.emit(
            turn,
            run_id,
            event_type,
            {
                **decision.to_metadata(),
                TURN_METADATA_COMPLETION_STATUS_FIELD: completion_result.status,
                TURN_METADATA_COMPLETION_REASON_FIELD: completion_result.reason,
            },
        )
