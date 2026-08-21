"""Lifecycle tests for in-process Agent run task ownership."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from functools import wraps
from pathlib import Path
from uuid import uuid4

import pytest

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunStatus
from opensprite_backend.conversations.sqlite_repository import (
    SqliteConversationRepository,
)
from opensprite_backend.inference.models import (
    ModelCompleted,
    ModelFinishReason,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
)
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import ToolRegistry


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


def store(tmp_path: Path) -> SqliteConversationRepository:
    return SqliteConversationRepository(
        build_app_paths(tmp_path / ".opensprite").database_file
    )


def start(repository: SqliteConversationRepository):
    return repository.start_run(
        conversation_id=None,
        client_request_id=str(uuid4()),
        message="hello",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run


@async_test
async def test_manager_owns_one_task_per_run_and_waits_for_completion(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = start(repository)

    class FinalGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            del request
            yield ModelTextDelta("done")
            yield ModelCompleted(ModelFinishReason.FINAL)

    manager = RunManager(
        repository,
        AgentLoop(
            repository=repository,
            gateway=FinalGateway(),
            tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        ),
    )

    assert await manager.start(run.id) is True
    assert await manager.start(run.id) is False
    result = await manager.wait(run.id)

    assert result is not None
    assert result.status is RunStatus.COMPLETED
    await manager.close()


@async_test
async def test_user_cancel_stops_running_task(tmp_path: Path) -> None:
    repository = store(tmp_path)
    run = start(repository)
    entered = asyncio.Event()

    class BlockingGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            del request
            entered.set()
            await asyncio.Event().wait()
            if False:
                yield ModelCompleted(ModelFinishReason.FINAL)

    manager = RunManager(
        repository,
        AgentLoop(
            repository=repository,
            gateway=BlockingGateway(),
            tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        ),
    )
    assert await manager.start(run.id) is True
    await asyncio.wait_for(entered.wait(), timeout=1)

    cancelling = await manager.cancel(run.id)
    result = await asyncio.wait_for(manager.wait(run.id), timeout=1)

    assert cancelling.status is RunStatus.CANCELLING
    assert result is not None
    assert result.status is RunStatus.CANCELLED
    await manager.close()


@async_test
async def test_close_marks_abandoned_running_work_interrupted(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = start(repository)
    entered = asyncio.Event()

    class BlockingGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            del request
            entered.set()
            await asyncio.Event().wait()
            if False:
                yield ModelCompleted(ModelFinishReason.FINAL)

    manager = RunManager(
        repository,
        AgentLoop(
            repository=repository,
            gateway=BlockingGateway(),
            tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        ),
    )
    assert await manager.start(run.id) is True
    await asyncio.wait_for(entered.wait(), timeout=1)

    await manager.close()

    persisted = repository.get_run(run.id)
    assert persisted is not None
    assert persisted.status is RunStatus.INTERRUPTED
