"""Post-response maintenance scheduling helpers."""

from __future__ import annotations

from typing import Awaitable, Callable

from ..utils.log import logger
from .background import CoalescingTaskScheduler


class PostResponseMaintenanceService:
    """Coordinates background document maintenance after an agent response."""

    def __init__(self):
        self._scheduler = CoalescingTaskScheduler[tuple[str, str]](
            on_rerun=lambda key: logger.info("[{}] maintenance.rerun | kind={}", key[1], key[0]),
        )
        self.tasks = self._scheduler.tasks
        self.rerun_keys = self._scheduler.rerun_keys

    def schedule(
        self,
        *,
        kind: str,
        session_id: str,
        runner: Callable[[str], Awaitable[None]],
    ) -> None:
        """Run one maintenance path in the background with per-session coalescing."""
        self._scheduler.schedule((kind, session_id), lambda: runner(session_id))

    def schedule_post_response(
        self,
        session_id: str,
        *,
        memory_runner: Callable[[str], Awaitable[None]],
        recent_summary_runner: Callable[[str], Awaitable[None]],
        user_profile_runner: Callable[[str], Awaitable[None]],
        active_task_runner: Callable[[str], Awaitable[None]],
    ) -> None:
        """Queue all post-response document maintenance jobs for one session."""
        self.schedule(kind="memory", session_id=session_id, runner=memory_runner)
        self.schedule(kind="recent_summary", session_id=session_id, runner=recent_summary_runner)
        self.schedule(kind="user_profile", session_id=session_id, runner=user_profile_runner)
        self.schedule(kind="active_task", session_id=session_id, runner=active_task_runner)

    async def wait(self) -> None:
        """Wait until all currently scheduled maintenance tasks finish."""
        await self._scheduler.wait()

    async def close(self) -> None:
        """Cancel and drain any in-flight maintenance tasks."""
        await self._scheduler.close()
