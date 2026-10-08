"""Lifecycle tests for in-process Agent run task ownership."""

from __future__ import annotations

import asyncio
from unittest.mock import patch
from collections.abc import AsyncIterator
from functools import wraps
from pathlib import Path
from uuid import uuid4

import pytest

from context_test_support import TestCapabilityResolver

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunEventType, RunStatus, StoreFailure
from opensprite_backend.conversations.repository import ConversationStoreError
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
from opensprite_backend.workspaces import (
    DEFAULT_WORKSPACE_ID,
    DefaultWorkspaceResolver,
)


DEFAULT_WORKSPACE = DefaultWorkspaceResolver().execution_context(
    DEFAULT_WORKSPACE_ID
)


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

            capability_resolver=TestCapabilityResolver(),
        ),
    )

    assert await manager.start(run.id, DEFAULT_WORKSPACE) is True
    assert await manager.start(run.id, DEFAULT_WORKSPACE) is False
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

            capability_resolver=TestCapabilityResolver(),
        ),
    )
    assert await manager.start(run.id, DEFAULT_WORKSPACE) is True
    await asyncio.wait_for(entered.wait(), timeout=1)

    cancelling = await manager.cancel(run.id)
    result = await asyncio.wait_for(manager.wait(run.id), timeout=1)

    assert cancelling.status is RunStatus.CANCELLING
    assert result is not None
    assert result.status is RunStatus.CANCELLED
    await manager.close()


@async_test
async def test_user_cancel_preserves_buffered_assistant_text(tmp_path: Path) -> None:
    repository = store(tmp_path)
    run = start(repository)
    buffered = asyncio.Event()

    class PartialGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            del request
            yield ModelTextDelta("visible ")
            yield ModelTextDelta("partial response")
            # The first chunk is visible; the second fast chunk is still
            # buffered and must be preserved when cancellation flushes it.
            buffered.set()
            await asyncio.Event().wait()

    manager = RunManager(
        repository,
        AgentLoop(
            repository=repository,
            gateway=PartialGateway(),

            capability_resolver=TestCapabilityResolver(),
        ),
    )
    try:
        with patch("opensprite_backend.agent.loop.monotonic", return_value=0.0):
            assert await manager.start(run.id, DEFAULT_WORKSPACE) is True
            await asyncio.wait_for(buffered.wait(), timeout=1)
        before_cancel = repository.get_run(run.id)
        assert before_cancel is not None
        assert before_cancel.partial_text == "visible "

        cancelling = await manager.cancel(run.id)
        result = await asyncio.wait_for(manager.wait(run.id), timeout=1)

        assert cancelling.status is RunStatus.CANCELLING
        assert result is not None
        assert result.status is RunStatus.CANCELLED
        assert result.error is None
        assert result.partial_text == "visible partial response"
        assert result.assistant_message_id is None
        events = repository.list_run_events(run.id, after_sequence=0, limit=100)
        assert [event.type for event in events][-2:] == [
            RunEventType.ASSISTANT_DELTA,
            RunEventType.RUN_CANCELLED,
        ]
        assert events[-2].data == {"text": "partial response"}
        assert all(event.type is not RunEventType.RUN_FAILED for event in events)
    finally:
        await manager.close()


@async_test
async def test_execution_store_failure_is_persisted_as_terminal_failure(
    tmp_path: Path,
) -> None:
    repository = store(tmp_path)
    run = start(repository)

    class FailingDeltaRepository:
        def __init__(self, wrapped: SqliteConversationRepository) -> None:
            self._wrapped = wrapped
            self._failed = False

        def append_assistant_delta(self, run_id: str, text: str):
            if not self._failed:
                self._failed = True
                raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE)
            return self._wrapped.append_assistant_delta(run_id, text)

        def __getattr__(self, name: str):
            return getattr(self._wrapped, name)

    failing_repository = FailingDeltaRepository(repository)

    class FinalGateway:
        async def stream(
            self,
            request: ModelRequest,
        ) -> AsyncIterator[ModelStreamEvent]:
            del request
            yield ModelTextDelta("done")
            yield ModelCompleted(ModelFinishReason.FINAL)

    manager = RunManager(
        failing_repository,  # type: ignore[arg-type]
        AgentLoop(
            repository=failing_repository,  # type: ignore[arg-type]
            gateway=FinalGateway(),

            capability_resolver=TestCapabilityResolver(),
        ),
    )

    assert await manager.start(run.id, DEFAULT_WORKSPACE) is True
    result = await manager.wait(run.id)

    assert result is not None
    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "internal_error"
    follow_up = repository.start_run(
        conversation_id=run.conversation_id,
        client_request_id=str(uuid4()),
        message="try again",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    )
    assert follow_up.run.status is RunStatus.QUEUED
    await manager.close()
