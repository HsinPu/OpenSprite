"""Concurrency and ownership tests for the in-process child-task pool."""

from __future__ import annotations

import asyncio

import pytest

from opensprite_backend.custom_agents.child_tasks import ChildTaskError, ChildTaskPool


def test_spawn_is_idempotent_and_checks_parent_and_depth() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def execute(parent_id: str, child_id: str) -> str:
            started.set()
            await release.wait()
            return f"{parent_id}:{child_id}"

        pool = ChildTaskPool(execute)
        first = await pool.spawn("parent", "child")
        duplicate = await pool.spawn("parent", "child")
        assert duplicate == first
        assert pool.get("parent", "child").state in {"queued", "running"}
        with pytest.raises(ChildTaskError, match="child_not_found"):
            pool.get("other-parent", "child")
        with pytest.raises(ChildTaskError, match="depth_exceeded"):
            await pool.spawn("parent", "nested", depth=2)

        await started.wait()
        release.set()
        completed = await pool.wait("parent", "child")
        assert completed.state == "completed"
        assert completed.result == "parent:child"
        # Completed records remain idempotent and are not restarted.
        assert await pool.spawn("parent", "child") == completed
        await pool.close()

    asyncio.run(scenario())


def test_parent_and_global_limits_do_not_allow_more_than_four_running() -> None:
    async def scenario() -> None:
        release = asyncio.Event()
        active = 0
        maximum = 0
        active_by_parent: dict[str, int] = {}

        async def execute(parent_id: str, child_id: str) -> str:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            active_by_parent[parent_id] = active_by_parent.get(parent_id, 0) + 1
            try:
                await release.wait()
                return child_id
            finally:
                active -= 1
                active_by_parent[parent_id] -= 1

        pool = ChildTaskPool(execute)
        tasks = [
            await pool.spawn(parent, f"child-{index}")
            for parent in ("p1", "p2", "p3")
            for index in range(2)
        ]
        await asyncio.sleep(0.05)
        assert active == 4
        assert maximum <= 4
        assert all(count <= 2 for count in active_by_parent.values())
        # The six-child creation quota belongs to each parent, not to the
        # whole pool.  A new parent is not blocked by p1/p2/p3's children.
        seventh_parent = await pool.spawn("p4", "child-0")
        release.set()
        results = await asyncio.gather(
            *(
                pool.wait(item.parent_id, item.child_id)
                for item in (*tasks, seventh_parent)
            )
        )
        assert all(item.state == "completed" for item in results)
        await pool.close()

    asyncio.run(scenario())


def test_timeout_includes_time_waiting_for_slots() -> None:
    async def scenario() -> None:
        release = asyncio.Event()

        async def execute(parent_id: str, child_id: str) -> None:
            await release.wait()

        pool = ChildTaskPool(
            execute,
            per_parent_limit=2,
            global_limit=1,
            maximum_tasks=2,
            timeout_seconds=0.05,
        )
        first = await pool.spawn("p1", "first")
        second = await pool.spawn("p2", "second")
        await asyncio.sleep(0.01)
        result = await pool.wait(second.parent_id, second.child_id)
        assert result.state == "timed_out"
        assert result.error == "timeout"
        await pool.cancel(first.parent_id, first.child_id)
        await pool.close()

    asyncio.run(scenario())


def test_cancel_and_cancel_parent_drain_tasks_with_safe_errors() -> None:
    async def scenario() -> None:
        release = asyncio.Event()

        async def execute(parent_id: str, child_id: str) -> None:
            await release.wait()

        pool = ChildTaskPool(execute)
        one = await pool.spawn("parent", "one")
        two = await pool.spawn("parent", "two")
        cancelled = await pool.cancel("parent", "one")
        assert cancelled.state == "cancelled"
        assert cancelled.error == "cancelled"
        assert await pool.spawn("parent", "one") == cancelled

        drained = await pool.cancel_parent("parent")
        assert {item.child_id for item in drained} == {"two"}
        assert all(item.state == "cancelled" for item in drained)
        assert all(item.error == "parent_cancelled" for item in drained)
        release.set()
        await pool.close()

    asyncio.run(scenario())


def test_close_drains_all_and_caller_wait_cancellation_is_not_swallowed() -> None:
    async def scenario() -> None:
        release = asyncio.Event()

        async def execute(parent_id: str, child_id: str) -> None:
            await release.wait()

        pool = ChildTaskPool(execute)
        child = await pool.spawn("parent", "child")
        waiter = asyncio.create_task(pool.wait("parent", "child"))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert pool.get("parent", "child").state in {"queued", "running"}

        await pool.close()
        result = pool.get(child.parent_id, child.child_id)
        assert result.state == "cancelled"
        assert result.error == "pool_closed"
        with pytest.raises(ChildTaskError, match="pool_closed"):
            await pool.spawn("parent", "new")

    asyncio.run(scenario())


def test_callback_failure_is_safe_and_does_not_leave_task() -> None:
    async def scenario() -> None:
        async def execute(parent_id: str, child_id: str) -> None:
            raise RuntimeError("secret callback details")

        pool = ChildTaskPool(execute)
        await pool.spawn("parent", "child")
        result = await pool.wait("parent", "child")
        assert result.state == "failed"
        assert result.error == "execution_failed"
        assert "secret" not in str(result)
        await pool.close()

    asyncio.run(scenario())


def test_each_parent_can_create_six_children_including_terminal_records() -> None:
    async def scenario() -> None:
        async def execute(parent_id: str, child_id: str) -> str:
            return child_id

        pool = ChildTaskPool(execute)
        for index in range(6):
            await pool.spawn("p1", f"child-{index}")
        results = await asyncio.gather(
            *(pool.wait("p1", f"child-{index}") for index in range(6))
        )
        assert all(item.state == "completed" for item in results)
        # Replaying an existing child is idempotent and does not consume a
        # seventh creation slot.
        assert (await pool.spawn("p1", "child-0")).state == "completed"
        with pytest.raises(ChildTaskError, match="capacity_exceeded"):
            await pool.spawn("p1", "child-6")
        # A different parent has an independent six-child allowance.
        await pool.spawn("p2", "child-0")
        assert (await pool.wait("p2", "child-0")).state == "completed"
        await pool.close()

    asyncio.run(scenario())


def test_parent_cancel_waits_for_executor_cleanup() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cancellation_seen = asyncio.Event()
        cleanup_finished = asyncio.Event()

        async def execute(parent_id: str, child_id: str) -> str:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancellation_seen.set()
                await cleanup_finished.wait()
                raise

        pool = ChildTaskPool(execute)
        await pool.spawn("parent", "child")
        await started.wait()
        cancel_task = asyncio.create_task(pool.cancel_parent("parent"))
        await cancellation_seen.wait()
        assert not cancel_task.done()
        cleanup_finished.set()
        result = (await cancel_task)[0]
        assert result.state == "cancelled"
        assert result.error == "parent_cancelled"
        await pool.close()

    asyncio.run(scenario())


def test_close_spawn_race_rejects_new_work_and_drains_existing() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cleanup_finished = asyncio.Event()

        async def execute(parent_id: str, child_id: str) -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await cleanup_finished.wait()
                raise

        pool = ChildTaskPool(execute)
        await pool.spawn("parent", "child")
        await started.wait()
        close_task = asyncio.create_task(pool.close())
        await asyncio.sleep(0)
        with pytest.raises(ChildTaskError, match="pool_closed"):
            await pool.spawn("parent", "after-close")
        assert not close_task.done()
        cleanup_finished.set()
        await close_task
        assert pool.get("parent", "child").state == "cancelled"

    asyncio.run(scenario())


def test_deadline_cannot_be_swallowed_into_success() -> None:
    async def scenario() -> None:
        async def execute(parent_id: str, child_id: str) -> str:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return "late result"

        pool = ChildTaskPool(execute, timeout_seconds=0.02)
        await pool.spawn("parent", "child")
        result = await pool.wait("parent", "child")
        assert result.state == "timed_out"
        assert result.result is None
        assert result.error == "timeout"
        await pool.close()

    asyncio.run(scenario())


def test_cancel_wins_when_executor_returns_during_cleanup() -> None:
    async def scenario() -> None:
        started = asyncio.Event()

        async def execute(parent_id: str, child_id: str) -> str:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return "cancelled result"

        pool = ChildTaskPool(execute)
        await pool.spawn("parent", "child")
        await started.wait()
        result = await pool.cancel("parent", "child")
        assert result.state == "cancelled"
        assert result.result is None
        await pool.close()

    asyncio.run(scenario())
