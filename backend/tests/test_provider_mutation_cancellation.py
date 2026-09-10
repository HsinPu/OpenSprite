import asyncio
from threading import Event

import pytest

from opensprite_backend.providers.mutations import _owned_thread


def test_repeated_cancellation_waits_for_worker_before_releasing_gate():
    async def scenario():
        entered, release = Event(), Event()
        gate = asyncio.Lock()
        def write():
            entered.set()
            assert release.wait(timeout=5)
        async def mutate():
            async with gate:
                await _owned_thread(write)
        task = asyncio.create_task(mutate())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert gate.locked()
            assert not task.done()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert not gate.locked()
    asyncio.run(scenario())
