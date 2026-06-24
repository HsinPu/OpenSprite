"""Runtime lifecycle helpers."""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Any

from .utils.log import logger


SHUTDOWN_STEP_TIMEOUT_SECONDS = 5.0


async def await_shutdown_step(
    awaitable: Any,
    *,
    name: str,
    timeout: float = SHUTDOWN_STEP_TIMEOUT_SECONDS,
) -> None:
    """Await one shutdown step without letting it block gateway exit forever."""

    try:
        await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Timed out stopping {}", name)


async def stop_background_task(task: asyncio.Task | None, *, name: str) -> None:
    """Cancel and await one runtime background task."""

    if task is None:
        return
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=SHUTDOWN_STEP_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Timed out stopping {}", name)
    except asyncio.CancelledError:
        logger.info("Stopped {}", name)


def install_shutdown_signal_handlers(shutdown_event: asyncio.Event) -> None:
    """Wire process signals to the runtime shutdown event when supported."""

    loop = asyncio.get_running_loop()

    def request_shutdown(signum: int) -> None:
        logger.info("Received shutdown signal {}; stopping gateway...", signum)
        shutdown_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
            loop.add_signal_handler(signum, request_shutdown, signum)
