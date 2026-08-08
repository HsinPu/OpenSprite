"""Keyed background task scheduler with rerun coalescing."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Hashable
from typing import Generic, TypeVar


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
