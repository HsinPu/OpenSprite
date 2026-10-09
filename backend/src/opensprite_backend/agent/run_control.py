"""One Run's enforcement state. No context, retry or continuation policy."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from copy import deepcopy
from time import monotonic
from typing import TypeVar

from .events import limit_failure
from .execution_errors import RunCancelled
from .plugin import ExecutionLimits

_T = TypeVar("_T")


class RunControl:
    def __init__(self, cancellation: asyncio.Event, limits: ExecutionLimits):
        self._cancellation = cancellation
        self._limits = deepcopy(limits)
        self._started_at = monotonic()
        self._deadline = self._started_at + limits.max_duration_seconds
        self._requests = self._summaries = self._generated_chars = self._operations = 0

    @property
    def limits(self) -> ExecutionLimits:
        return deepcopy(self._limits)

    @property
    def cancellation_requested(self) -> bool:
        return self._cancellation.is_set()

    @property
    def expired(self) -> bool:
        return monotonic() >= self._deadline

    def deadline_failure(self):
        return limit_failure("duration_seconds", self._limits.max_duration_seconds,
                             round(max(0, monotonic() - self._started_at), 6))

    def check_cancelled(self) -> None:
        if self.cancellation_requested:
            raise RunCancelled()

    def check(self) -> None:
        self.check_cancelled()
        if self.expired:
            raise self.deadline_failure()

    async def checkpoint(self) -> None:
        self.check()
        await asyncio.sleep(0)
        self.check()

    def check_request(self, *, summary: bool = False) -> None:
        self.check()
        if self._requests >= self._limits.max_model_requests:
            raise limit_failure("model_requests", self._limits.max_model_requests, self._requests)
        if summary and self._summaries >= self._limits.max_compactions:
            raise limit_failure("summary_requests", self._limits.max_compactions, self._summaries)

    def consume_request(self, *, summary: bool = False) -> None:
        self.check_request(summary=summary)
        self._requests += 1
        self._summaries += int(summary)

    def consume_text(self, size: int) -> None:
        self.check()
        if self._generated_chars + size > self._limits.max_text_chars:
            raise limit_failure("generated_chars", self._limits.max_text_chars, self._generated_chars)
        self._generated_chars += size

    def consume_operation(self) -> None:
        self.check()
        if self._operations >= 2048:
            raise limit_failure("host_operations", 2048, self._operations)
        self._operations += 1

    async def wait(self, awaitable: Awaitable[_T]) -> _T:
        operation = asyncio.ensure_future(awaitable)
        cancelled = asyncio.create_task(self._cancellation.wait())
        timeout = asyncio.timeout(max(0, self._deadline - monotonic()))
        try:
            self.check()
            try:
                async with timeout:
                    done, _ = await asyncio.wait({operation, cancelled}, return_when=asyncio.FIRST_COMPLETED)
                    self.check()
                    if cancelled in done and cancelled.result():
                        raise RunCancelled()
                    return operation.result()
            except TimeoutError:
                self.check_cancelled()
                if timeout.expired():
                    raise self.deadline_failure() from None
                raise
        finally:
            for task in (operation, cancelled):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation, cancelled, return_exceptions=True)

    async def stream(self, iterator: AsyncIterator[_T]) -> AsyncIterator[_T]:
        try:
            while True:
                try:
                    yield await self.wait(anext(iterator))
                except StopAsyncIteration:
                    return
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                with suppress(Exception):
                    await close()
