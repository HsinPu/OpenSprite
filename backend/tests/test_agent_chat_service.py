"""Application-service tests for accepting and observing Agent Runs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path

import pytest

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.application import (
    AgentChatError,
    AgentChatService,
    ChatErrorCode,
)
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
from opensprite_backend.models import (
    AiSettings,
    ModelSelection,
    OpenRouterModelListResponse,
    ProviderListResponse,
    ProviderStatus,
    ProviderSummary,
    ResponseMode,
)
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from opensprite_backend.tools.registry import ToolRegistry


def async_test(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class FixedSettings:
    def __init__(self, settings: AiSettings) -> None:
        self.settings = settings

    async def get(self) -> AiSettings:
        return self.settings

    async def put(self, payload: AiSettings) -> AiSettings:
        self.settings = payload
        return payload


class FixedConnections:
    def __init__(self, connected: set[str]) -> None:
        self.connected = connected

    async def list_providers(self) -> ProviderListResponse:
        providers = []
        for provider_id, name in (
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("openrouter", "OpenRouter"),
        ):
            is_connected = provider_id in self.connected
            providers.append(
                ProviderSummary(
                    id=provider_id,
                    name=name,
                    connected=is_connected,
                    status=(
                        ProviderStatus.CONNECTED
                        if is_connected
                        else ProviderStatus.DISCONNECTED
                    ),
                    credentialPreview="••••test" if is_connected else None,
                    lastCheckedAt=(
                        datetime(2026, 8, 21, 8, tzinfo=UTC)
                        if is_connected
                        else None
                    ),
                )
            )
        return ProviderListResponse(providers=providers)

    async def list_openrouter_models(self) -> OpenRouterModelListResponse:
        raise AssertionError

    async def connect(self, provider_id, api_key):
        del provider_id, api_key
        raise AssertionError

    async def test(self, provider_id):
        del provider_id
        raise AssertionError

    async def disconnect(self, provider_id):
        del provider_id
        raise AssertionError


class FinalGateway:
    async def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[ModelStreamEvent]:
        assert request.provider_id == "openrouter"
        assert request.model_id == "openrouter/auto"
        assert request.response_mode == "default"
        yield ModelTextDelta("真實流程回覆")
        yield ModelCompleted(ModelFinishReason.FINAL)


def service(tmp_path: Path, *, model: bool = True, connected: bool = True):
    repository = SqliteConversationRepository(
        build_app_paths(tmp_path / ".opensprite").database_file
    )
    settings = AiSettings(
        model=(
            ModelSelection(
                providerId="openrouter",
                modelId="openrouter/auto",
                contextBudget="auto",
            )
            if model
            else None
        ),
        responseMode=ResponseMode.DEFAULT,
    )
    loop = AgentLoop(
        repository=repository,
        gateway=FinalGateway(),
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
    )
    manager = RunManager(repository, loop)
    chat = AgentChatService(
        repository,
        FixedSettings(settings),
        FixedConnections({"openrouter"} if connected else set()),
        manager,
        event_poll_seconds=0.001,
    )
    return chat, repository, manager


@async_test
async def test_start_run_persists_then_executes_and_lists_real_data(
    tmp_path: Path,
) -> None:
    chat, repository, manager = service(tmp_path)

    accepted = await chat.start_run(
        conversation_id=None,
        client_request_id="e898796c-71e9-4eb5-aac1-7a6e9430a429",
        message="整理今天的工作",
    )
    completed = await manager.wait(accepted.run.id)

    assert completed is not None
    assert completed.status is RunStatus.COMPLETED
    conversations = await chat.list_conversations(limit=50, before=None)
    assert [item.id for item in conversations.items] == [accepted.conversation.id]
    messages = await chat.list_messages(
        accepted.conversation.id,
        limit=100,
        before_sequence=None,
    )
    assert [(item.role, item.content) for item in messages.items] == [
        ("user", "整理今天的工作"),
        ("assistant", "真實流程回覆"),
    ]
    assert repository.database_file.is_file()
    await chat.close()


@async_test
async def test_start_is_idempotent_and_does_not_duplicate_execution(
    tmp_path: Path,
) -> None:
    chat, _repository, manager = service(tmp_path)
    request_id = "e898796c-71e9-4eb5-aac1-7a6e9430a429"

    first = await chat.start_run(
        conversation_id=None,
        client_request_id=request_id,
        message="hello",
    )
    replay = await chat.start_run(
        conversation_id=None,
        client_request_id=request_id,
        message="hello",
    )
    await manager.wait(first.run.id)

    assert replay.replayed is True
    assert replay.run.id == first.run.id
    await chat.close()


@pytest.mark.parametrize(
    ("model", "connected", "code"),
    [
        (False, True, ChatErrorCode.MODEL_NOT_SELECTED),
        (True, False, ChatErrorCode.PROVIDER_NOT_CONNECTED),
    ],
)
def test_start_requires_selected_connected_provider(
    tmp_path: Path,
    model: bool,
    connected: bool,
    code: ChatErrorCode,
) -> None:
    async def scenario() -> None:
        chat, _repository, _manager = service(
            tmp_path,
            model=model,
            connected=connected,
        )
        with pytest.raises(AgentChatError) as captured:
            await chat.start_run(
                conversation_id=None,
                client_request_id="e898796c-71e9-4eb5-aac1-7a6e9430a429",
                message="hello",
            )
        assert captured.value.code is code
        await chat.close()

    asyncio.run(scenario())


@async_test
async def test_event_stream_replays_from_sequence_and_ends_at_terminal(
    tmp_path: Path,
) -> None:
    chat, _repository, manager = service(tmp_path)
    accepted = await chat.start_run(
        conversation_id=None,
        client_request_id="e898796c-71e9-4eb5-aac1-7a6e9430a429",
        message="hello",
    )
    await manager.wait(accepted.run.id)

    events = [
        event
        async for event in chat.stream_events(
            accepted.run.id,
            after_sequence=1,
        )
    ]

    assert [event.sequence for event in events] == [2, 3, 4]
    assert events[-1].type.value == "run.completed"
    await chat.close()


@async_test
async def test_startup_interrupts_existing_non_terminal_runs(
    tmp_path: Path,
) -> None:
    chat, repository, _manager = service(tmp_path)
    queued = repository.start_run(
        conversation_id=None,
        client_request_id="e898796c-71e9-4eb5-aac1-7a6e9430a429",
        message="queued",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    ).run

    interrupted = await chat.startup()

    assert interrupted == (queued.id,)
    persisted = repository.get_run(queued.id)
    assert persisted is not None
    assert persisted.status is RunStatus.INTERRUPTED
    await chat.close()
