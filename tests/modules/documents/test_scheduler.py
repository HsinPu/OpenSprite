import asyncio

from opensprite.modules.documents.scheduler import CoalescingTaskScheduler


def test_scheduler_coalesces_concurrent_requests_into_one_rerun():
    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()
        calls: list[int] = []
        reruns: list[str] = []

        async def runner():
            calls.append(len(calls) + 1)
            if len(calls) == 1:
                started.set()
                await release.wait()

        scheduler = CoalescingTaskScheduler[str](on_rerun=reruns.append)
        assert scheduler.schedule("session-1", runner) is True
        await started.wait()
        assert scheduler.schedule("session-1", runner) is False
        assert scheduler.schedule("session-1", runner) is False
        release.set()

        await scheduler.wait()

        assert calls == [1, 2]
        assert reruns == ["session-1"]
        assert scheduler.tasks == {}
        assert scheduler.rerun_keys == set()

    asyncio.run(scenario())


def test_scheduler_reports_runner_exceptions_and_cleans_up():
    async def scenario():
        failures: list[tuple[str, str]] = []

        async def runner():
            raise ValueError("boom")

        scheduler = CoalescingTaskScheduler[str](
            on_exception=lambda key, exc: failures.append((key, str(exc)))
        )
        assert scheduler.schedule("session-1", runner) is True

        await scheduler.wait()

        assert failures == [("session-1", "boom")]
        assert scheduler.tasks == {}

    asyncio.run(scenario())


def test_scheduler_reports_missing_running_loop_without_leaking_a_task():
    failures: list[tuple[str, RuntimeError]] = []

    async def runner():
        return None

    scheduler = CoalescingTaskScheduler[str](
        on_schedule_error=lambda key, exc: failures.append((key, exc))
    )

    assert scheduler.schedule("session-1", runner) is False
    assert len(failures) == 1
    assert failures[0][0] == "session-1"
    assert isinstance(failures[0][1], RuntimeError)
    assert scheduler.tasks == {}


def test_scheduler_close_cancels_and_drains_in_flight_tasks():
    async def scenario():
        started = asyncio.Event()
        cancelled = asyncio.Event()
        never_finishes = asyncio.Event()

        async def runner():
            started.set()
            try:
                await never_finishes.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        scheduler = CoalescingTaskScheduler[str]()
        assert scheduler.schedule("session-1", runner) is True
        await started.wait()

        await scheduler.close()

        assert cancelled.is_set()
        assert scheduler.tasks == {}
        assert scheduler.rerun_keys == set()

    asyncio.run(scenario())
