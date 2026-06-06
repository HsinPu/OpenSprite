"""Background task coordination and process notification helpers for agent services."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Hashable
import time
from typing import Any, Generic, TypeVar

from ..bus.events import InboundMessage
from ..tools.process_runtime import BackgroundSession
from ..tools.shell_runtime import format_captured_output

K = TypeVar("K", bound=Hashable)


class CoalescingTaskScheduler(Generic[K]):
    """Run at most one background task per key, then rerun once if requested."""

    def __init__(
        self,
        *,
        on_exception: Callable[[K, Exception], None] | None = None,
        on_rerun: Callable[[K], None] | None = None,
        on_schedule_error: Callable[[K, RuntimeError], None] | None = None,
    ):
        self._tasks: dict[K, asyncio.Task[None]] = {}
        self._rerun: set[K] = set()
        self._on_exception = on_exception
        self._on_rerun = on_rerun
        self._on_schedule_error = on_schedule_error

    @property
    def tasks(self) -> dict[K, asyncio.Task[None]]:
        """Expose current task bookkeeping for existing diagnostics/tests."""
        return self._tasks

    @property
    def rerun_keys(self) -> set[K]:
        """Expose pending rerun bookkeeping for existing diagnostics/tests."""
        return self._rerun

    def schedule(self, key: K, runner: Callable[[], Awaitable[None]]) -> bool:
        """Schedule a keyed runner, coalescing concurrent calls into one rerun."""
        existing = self._tasks.get(key)
        if existing is not None and not existing.done():
            self._rerun.add(key)
            return False

        task: asyncio.Task[None] | None = None

        async def _run() -> None:
            try:
                while True:
                    self._rerun.discard(key)
                    try:
                        await runner()
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        if self._on_exception is None:
                            raise
                        self._on_exception(key, exc)
                    if key not in self._rerun:
                        break
                    if self._on_rerun is not None:
                        self._on_rerun(key)
            except asyncio.CancelledError:
                pass
            finally:
                if task is not None and self._tasks.get(key) is task:
                    self._tasks.pop(key, None)
                self._rerun.discard(key)

        try:
            task = asyncio.get_running_loop().create_task(_run())
        except RuntimeError as exc:
            if self._on_schedule_error is None:
                raise
            self._on_schedule_error(key, exc)
            return False
        self._tasks[key] = task
        return True

    async def wait(self) -> None:
        """Wait until all currently scheduled tasks and coalesced reruns finish."""
        while True:
            tasks = [task for task in self._tasks.values() if not task.done()]
            if not tasks:
                return
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self) -> None:
        """Cancel and drain any in-flight tasks."""
        tasks = [task for task in self._tasks.values() if not task.done()]
        self._tasks.clear()
        self._rerun.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class BackgroundSessionNotificationService:
    """Formats and publishes background session completion notices."""

    def __init__(
        self,
        *,
        message_bus_getter: Callable[[], Any],
        save_message: Callable[..., Awaitable[None]],
    ):
        self._message_bus_getter = message_bus_getter
        self._save_message = save_message

    @staticmethod
    def format_summary_request(session: BackgroundSession) -> str:
        """Render the internal request asking the agent to summarize a completed process."""
        output_tail = format_captured_output(
            session.output_chunks,
            max_chars=1200,
        )
        runtime_seconds = max(
            0.0,
            (session.finished_at or time.monotonic()) - session.started_at,
        )
        return "\n".join(
            [
                "A managed background process has finished. Summarize the result for the user.",
                f"Session ID: {session.session_id}",
                f"Command: {session.command}",
                f"Termination: {session.termination_reason or 'exit'}",
                f"Exit code: {session.exit_code}",
                f"Runtime: {runtime_seconds:.2f}s",
                "Keep the reply concise. Mention whether it succeeded, failed, or was stopped. Include only the most relevant output details.",
                "Output tail:",
                output_tail,
            ]
        )

    @staticmethod
    def format_exit_message(session: BackgroundSession) -> str:
        """Backward-compatible alias for the agent summary request text."""
        return BackgroundSessionNotificationService.format_summary_request(session)

    def make_exit_notifier(
        self,
        *,
        channel: str | None,
        external_chat_id: str | None,
        session_id: str | None,
    ) -> Callable[[BackgroundSession], Awaitable[None]] | None:
        """Build an outbound notifier for managed background session completion."""
        bus = self._message_bus_getter()
        if not bus or not channel or external_chat_id is None or session_id is None:
            return None

        ch = channel
        tid = str(external_chat_id)
        sid = session_id

        async def _notify(session: BackgroundSession) -> None:
            content = self.format_summary_request(session)
            metadata = {
                "channel": ch,
                "external_chat_id": tid,
                "kind": "background_session_summary_request",
                "session_id": session.session_id,
                "termination_reason": session.termination_reason or "exit",
                "exit_code": session.exit_code,
                "_bypass_commands": True,
            }
            await bus.publish_inbound(
                InboundMessage(
                    channel=ch,
                    sender_id="system:background",
                    sender_name="background process",
                    external_chat_id=tid,
                    session_id=sid,
                    content=content,
                    metadata=metadata,
                )
            )

        return _notify
