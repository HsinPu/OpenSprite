"""In-process ownership and bounded concurrency for one parent Agent run.

This module is deliberately independent from the Agent loop and persistence
layers.  A parent run owns child tasks by the pair ``(parent_id, child_id)``;
the pool keeps their lifecycle in memory only.  The caller is responsible for
enforcing that a child cannot create another child (depth is accepted as an
explicit boundary check here, but no recursive ownership model is provided).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Awaitable, Callable, Literal, TypeAlias


ChildTaskState: TypeAlias = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "timed_out",
]
ChildExecutor: TypeAlias = Callable[[str, str], Awaitable[object]]


class ChildTaskError(Exception):
    """Safe, path-free lifecycle error exposed by the child-task boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ChildTaskRecord:
    """An immutable public view of a child task's in-memory lifecycle."""

    parent_id: str
    child_id: str
    state: ChildTaskState
    result: object | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, object | None]:
        """Return the stable transport-shaped view used by future callers."""

        return {
            "parentId": self.parent_id,
            "childId": self.child_id,
            "state": self.state,
            "result": self.result,
            "error": self.error,
        }


@dataclass(slots=True)
class _OwnedTask:
    record: ChildTaskRecord
    task: asyncio.Task[None]
    deadline: float
    cancel_error: str | None = None


class ChildTaskPool:
    """Own bounded asynchronous child execution without a parent semaphore.

    ``executor`` must be an async callable receiving ``(parent_id, child_id)``
    and returning the child result.  ``spawn`` schedules work and returns a
    queued/running record; use ``wait`` to await its terminal record.  The
    default limits are two concurrently executing children per parent, four
    concurrently executing children globally, and six distinct child IDs
    created by each parent (including terminal records).  There is no global
    creation quota.  The timeout starts at ``spawn`` and therefore includes
    time spent waiting for limits.

    The delegation coordinator supplies persistence and runtime integration.
    Executors must cooperate with cancellation; cleanup is drained before slots
    are released. A callback cannot turn an observed deadline/cancel into success.
    """

    def __init__(
        self,
        executor: ChildExecutor,
        *,
        per_parent_limit: int = 2,
        global_limit: int = 4,
        maximum_tasks: int = 6,
        timeout_seconds: float = 600.0,
    ) -> None:
        if not callable(executor):
            raise ValueError("executor_required")
        if (
            type(per_parent_limit) is not int
            or per_parent_limit < 1
            or type(global_limit) is not int
            or global_limit < 1
            or type(maximum_tasks) is not int
            or maximum_tasks < 1
            or type(timeout_seconds) not in {int, float}
            or timeout_seconds <= 0
        ):
            raise ValueError("invalid_limits")
        self._executor = executor
        self._per_parent_limit = per_parent_limit
        self._global_limit = global_limit
        # ``maximum_tasks`` names the per-parent creation quota.  It is
        # intentionally independent of the global running semaphore: one
        # parent must not consume another parent's creation allowance.
        self._maximum_children_per_parent = maximum_tasks
        self._timeout_seconds = float(timeout_seconds)

        self._lock = asyncio.Lock()
        self._global_slots = asyncio.Semaphore(global_limit)
        self._parent_slots: dict[str, asyncio.Semaphore] = {}
        self._owned: dict[tuple[str, str], _OwnedTask] = {}
        self._records: dict[tuple[str, str], ChildTaskRecord] = {}
        self._created_count: dict[str, int] = {}
        self._cancelling_parents: set[str] = set()
        self._closed = False

    async def spawn(
        self,
        parent_id: str,
        child_id: str,
        *,
        depth: int = 1,
    ) -> ChildTaskRecord:
        """Schedule one child, or return its existing record idempotently.

        A child ID is unique only within its parent.  Terminal entries remain
        in memory so a later duplicate spawn cannot restart completed work.
        ``depth`` is intentionally restricted to one; a caller boundary must
        pass the appropriate value when accepting a child request.
        """

        _validate_identifier(parent_id)
        _validate_identifier(child_id)
        if type(depth) is not int or depth != 1:
            raise ChildTaskError("depth_exceeded")
        key = (parent_id, child_id)
        loop = asyncio.get_running_loop()
        async with self._lock:
            if self._closed:
                raise ChildTaskError("pool_closed")
            if parent_id in self._cancelling_parents:
                raise ChildTaskError("parent_cancelling")
            existing = self._records.get(key)
            if existing is not None:
                return existing
            if self._created_count.get(parent_id, 0) >= self._maximum_children_per_parent:
                raise ChildTaskError("capacity_exceeded")

            parent_slots = self._parent_slots.setdefault(
                parent_id,
                asyncio.Semaphore(self._per_parent_limit),
            )
            record = ChildTaskRecord(parent_id, child_id, "queued")
            deadline = loop.time() + self._timeout_seconds
            task = asyncio.create_task(
                self._run(key, parent_slots, deadline),
                name=f"opensprite-child-{parent_id}-{child_id}",
            )
            self._owned[key] = _OwnedTask(record, task, deadline)
            self._records[key] = record
            self._created_count[parent_id] = self._created_count.get(parent_id, 0) + 1
            return record

    def get(self, parent_id: str, child_id: str) -> ChildTaskRecord:
        """Return a child record after enforcing parent ownership."""

        key = self._owned_key(parent_id, child_id)
        # This method is intentionally synchronous for status polling.  All
        # writes happen on the event loop, so a short dictionary read cannot
        # interleave with an update in the same loop turn.
        record = self._records.get(key)
        if record is None:
            raise ChildTaskError("child_not_found")
        return record

    async def wait(self, parent_id: str, child_id: str) -> ChildTaskRecord:
        """Wait for a child without allowing caller cancellation to orphan it."""

        key = self._owned_key(parent_id, child_id)
        owned = self._owned.get(key)
        if owned is not None:
            # Shield keeps a cancelled HTTP/request task from cancelling the
            # owned child.  The caller's CancelledError is intentionally not
            # swallowed and propagates after this await is interrupted.
            await asyncio.shield(owned.task)
        return self.get(parent_id, child_id)

    async def cancel(self, parent_id: str, child_id: str) -> ChildTaskRecord:
        """Request one child cancellation and await its independent outcome."""

        key = self._owned_key(parent_id, child_id)
        async with self._lock:
            owned = self._owned.get(key)
            if owned is None:
                if key in self._records:
                    return self._records[key]
                raise ChildTaskError("child_not_found")
            if owned.record.state in {
                "completed",
                "failed",
                "cancelled",
                "timed_out",
            }:
                return owned.record
            owned.cancel_error = "cancelled"
            owned.task.cancel()
            task = owned.task
            owned_snapshot = owned
        caller = asyncio.current_task()
        cancellation_count = caller.cancelling() if caller is not None else 0
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            # A task cancelled before its first event-loop step never enters
            # ``_run`` and therefore cannot record its own state.
            caller_cancelled = (
                caller is not None and caller.cancelling() > cancellation_count
            )
            if task.cancelled() and not caller_cancelled:
                await self._finish(key, "cancelled", error="cancelled")
            if caller_cancelled:
                # The caller requested cancellation while this method was
                # draining the owned task.  Finish the child before
                # propagating the caller's own CancelledError.
                await self._drain((task,))
                await self._finalize_cancelled((owned_snapshot,), "cancelled")
                raise
            if not task.cancelled():
                raise
        return self.get(parent_id, child_id)

    async def cancel_parent(self, parent_id: str) -> tuple[ChildTaskRecord, ...]:
        """Cancel and drain every currently owned child for one parent."""

        _validate_identifier(parent_id)
        async with self._lock:
            if self._closed:
                raise ChildTaskError("pool_closed")
            self._cancelling_parents.add(parent_id)
            owned = tuple(
                item
                for (owner, _), item in self._owned.items()
                if owner == parent_id
                and item.record.state
                in {"queued", "running"}
            )
            for item in owned:
                item.cancel_error = "parent_cancelled"
                item.task.cancel()
            tasks = tuple(item.task for item in owned)
        try:
            await self._drain(tasks)
        finally:
            await self._finalize_cancelled(owned, "parent_cancelled")
            async with self._lock:
                self._cancelling_parents.discard(parent_id)
        return tuple(self.get(parent_id, item.record.child_id) for item in owned)

    async def forget_parent(self, parent_id: str) -> None:
        """Release terminal in-memory results after their parent has finished."""
        async with self._lock:
            if any(key[0] == parent_id for key in self._owned):
                raise ChildTaskError("parent_busy")
            for key in tuple(self._records):
                if key[0] == parent_id:
                    del self._records[key]
            self._parent_slots.pop(parent_id, None)
            self._created_count.pop(parent_id, None)
            self._cancelling_parents.discard(parent_id)

    async def close(self) -> None:
        """Close the pool and drain all owned tasks without leaving orphans."""

        async with self._lock:
            if self._closed:
                return
            self._closed = True
            owned = tuple(
                item
                for item in self._owned.values()
                if item.record.state in {"queued", "running"}
            )
            for item in owned:
                item.cancel_error = "pool_closed"
                item.task.cancel()
            tasks = tuple(item.task for item in owned)
        try:
            await self._drain(tasks)
        finally:
            await self._finalize_cancelled(owned, "pool_closed")

    async def _run(
        self,
        key: tuple[str, str],
        parent_slots: asyncio.Semaphore,
        deadline: float,
    ) -> None:
        parent_acquired = False
        global_acquired = False
        try:
            # Give cancellation requested immediately after ``spawn`` a
            # suspension point inside this handler.  Without this first
            # yield, asyncio can cancel a never-started task before it has a
            # chance to record its terminal state.
            await asyncio.sleep(0)
            remaining = self._remaining(deadline)
            await asyncio.wait_for(parent_slots.acquire(), remaining)
            parent_acquired = True
            remaining = self._remaining(deadline)
            await asyncio.wait_for(self._global_slots.acquire(), remaining)
            global_acquired = True
            await self._set_state(key, "running")
            remaining = self._remaining(deadline)
            result = await asyncio.wait_for(
                self._executor(key[0], key[1]),
                remaining,
            )
            await self._finish(key, "completed", result=result)
        except TimeoutError:
            await self._finish(key, "timed_out", error="timeout")
        except asyncio.CancelledError:
            error = await self._cancel_error(key)
            await self._finish(key, "cancelled", error=error)
        except Exception:
            # Do not expose callback exception text, which could contain
            # prompt, credential, or filesystem details.
            await self._finish(key, "failed", error="execution_failed")
        finally:
            if global_acquired:
                self._global_slots.release()
            if parent_acquired:
                parent_slots.release()

    async def _set_state(self, key: tuple[str, str], state: ChildTaskState) -> None:
        async with self._lock:
            owned = self._owned.get(key)
            if owned is None or owned.record.state in {
                "completed",
                "failed",
                "cancelled",
                "timed_out",
            }:
                return
            owned.record = replace(owned.record, state=state)
            self._records[key] = owned.record

    async def _finish(
        self,
        key: tuple[str, str],
        state: ChildTaskState,
        *,
        result: object | None = None,
        error: str | None = None,
    ) -> None:
        async with self._lock:
            owned = self._owned.get(key)
            if owned is None:
                return
            if owned.record.state in {
                "completed",
                "failed",
                "cancelled",
                "timed_out",
            }:
                return
            if owned.cancel_error is not None:
                state, result, error = "cancelled", None, owned.cancel_error
            elif state == "completed" and asyncio.get_running_loop().time() >= owned.deadline:
                state, result, error = "timed_out", None, "timeout"
            owned.record = replace(
                owned.record,
                state=state,
                result=result,
                error=error,
            )
            self._records[key] = owned.record
            self._owned.pop(key, None)

    async def _finalize_cancelled(
        self,
        owned: tuple[_OwnedTask, ...],
        error: str,
    ) -> None:
        for item in owned:
            if item.task.cancelled():
                await self._finish(
                    (item.record.parent_id, item.record.child_id),
                    "cancelled",
                    error=error,
                )

    async def _cancel_error(self, key: tuple[str, str]) -> str:
        async with self._lock:
            owned = self._owned.get(key)
            return owned.cancel_error if owned and owned.cancel_error else "cancelled"

    async def _drain(self, tasks: tuple[asyncio.Task[None], ...]) -> None:
        if not tasks:
            return
        async def gather_owned() -> None:
            await asyncio.gather(*tasks, return_exceptions=True)

        drain = asyncio.create_task(gather_owned(), name="opensprite-child-drain")
        cancelled = False
        try:
            await asyncio.shield(drain)
        except asyncio.CancelledError:
            cancelled = True
            await asyncio.shield(drain)
        if cancelled:
            raise asyncio.CancelledError

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError
        return remaining

    @staticmethod
    def _owned_key(parent_id: str, child_id: str) -> tuple[str, str]:
        _validate_identifier(parent_id)
        _validate_identifier(child_id)
        return parent_id, child_id


def _validate_identifier(value: str) -> None:
    if type(value) is not str or not value:
        raise ChildTaskError("invalid_request")
