"""In-memory state for active user-facing runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time


@dataclass
class ActiveRunState:
    """In-memory state for one currently active user-facing run."""

    session_id: str
    run_id: str
    started_at: float
    cancel_requested: bool = False
    cancel_requested_at: float | None = None


class RunBusyError(RuntimeError):
    """Raised when the same session already has an active run."""


class RunCancelledError(asyncio.CancelledError):
    """Raised when cooperative cancellation is requested for an active run."""


class AgentRunStateService:
    """Tracks one active run per session and handles cooperative cancel requests."""

    def __init__(self):
        self._active_by_session: dict[str, ActiveRunState] = {}

    def ensure_available(self, session_id: str) -> None:
        """Reject a new turn before it performs any input side effects."""
        existing = self._active_by_session.get(session_id)
        if existing is not None:
            raise RunBusyError(
                f"Session '{session_id}' is already processing run '{existing.run_id}'."
            )

    def start(self, session_id: str, run_id: str) -> ActiveRunState:
        existing = self._active_by_session.get(session_id)
        if existing is not None and existing.run_id != run_id:
            raise RunBusyError(
                f"Session '{session_id}' is already processing run '{existing.run_id}'."
            )
        active = ActiveRunState(session_id=session_id, run_id=run_id, started_at=time.time())
        self._active_by_session[session_id] = active
        return active

    def finish(self, session_id: str, run_id: str) -> None:
        existing = self._active_by_session.get(session_id)
        if existing is not None and existing.run_id == run_id:
            self._active_by_session.pop(session_id, None)

    def get_active(self, session_id: str) -> ActiveRunState | None:
        return self._active_by_session.get(session_id)

    def is_active(self, session_id: str, run_id: str) -> bool:
        active = self._active_by_session.get(session_id)
        return active is not None and active.run_id == run_id

    def request_cancel(self, session_id: str, run_id: str) -> ActiveRunState | None:
        active = self._active_by_session.get(session_id)
        if active is None or active.run_id != run_id:
            return None
        if not active.cancel_requested:
            active.cancel_requested = True
            active.cancel_requested_at = time.time()
        return active

    def is_cancel_requested(self, session_id: str, run_id: str) -> bool:
        active = self._active_by_session.get(session_id)
        return bool(active is not None and active.run_id == run_id and active.cancel_requested)
