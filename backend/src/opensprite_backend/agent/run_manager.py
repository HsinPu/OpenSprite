"""In-process ownership for background Agent tasks and user cancellation."""

from __future__ import annotations

import asyncio

from opensprite_backend.conversations.models import (
    RunSnapshot,
    RunStatus,
    StoreFailure,
)
from opensprite_backend.conversations.repository import (
    ConversationRepository,
    ConversationStoreError,
)

from .loop import AgentLoop


class RunManager:
    def __init__(
        self,
        repository: ConversationRepository,
        loop: AgentLoop,
    ) -> None:
        self._repository = repository
        self._loop = loop
        self._tasks: dict[str, asyncio.Task[RunSnapshot]] = {}
        self._cancellations: dict[str, asyncio.Event] = {}
        self._closed = False
        self._lock = asyncio.Lock()

    async def start(self, run_id: str) -> bool:
        async with self._lock:
            if self._closed:
                raise RuntimeError("run manager is closed")
            existing = self._tasks.get(run_id)
            if existing is not None and not existing.done():
                return False
            run = await asyncio.to_thread(self._repository.get_run, run_id)
            if run is None:
                raise ConversationStoreError(StoreFailure.NOT_FOUND)
            if run.status is not RunStatus.QUEUED:
                return False
            cancellation = asyncio.Event()
            task = asyncio.create_task(
                self._loop.execute(run_id, cancellation),
                name=f"opensprite-run-{run_id}",
            )
            self._tasks[run_id] = task
            self._cancellations[run_id] = cancellation
            task.add_done_callback(
                lambda completed, owned_run_id=run_id: self._discard(
                    owned_run_id,
                    completed,
                )
            )
            return True

    async def cancel(self, run_id: str) -> RunSnapshot:
        async with self._lock:
            cancellation = self._cancellations.get(run_id)
            result = await asyncio.to_thread(
                self._repository.request_cancel,
                run_id,
            )
            if cancellation is not None:
                cancellation.set()
            return result

    async def wait(self, run_id: str) -> RunSnapshot | None:
        async with self._lock:
            task = self._tasks.get(run_id)
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
        return await asyncio.to_thread(self._repository.get_run, run_id)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            tasks = tuple(self._tasks.values())
            for task in tasks:
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.to_thread(self._repository.interrupt_incomplete_runs)
        self._tasks.clear()
        self._cancellations.clear()

    def _discard(
        self,
        run_id: str,
        task: asyncio.Task[RunSnapshot],
    ) -> None:
        if self._tasks.get(run_id) is task:
            self._tasks.pop(run_id, None)
            self._cancellations.pop(run_id, None)
        if not task.cancelled():
            task.exception()
