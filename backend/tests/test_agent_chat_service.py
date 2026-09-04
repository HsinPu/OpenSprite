"""Application-service tests for accepting and observing Agent Runs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from threading import Event

import pytest

from context_test_support import TestCapabilityResolver

from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.application import (
    AgentChatError,
    AgentChatService,
    ChatErrorCode,
)
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunStatus
from opensprite_backend.conversations.models import RunEventType
from opensprite_backend.conversations.event_notifier import RunEventNotifier
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
from opensprite_backend.schedules.models import ExecutionProfile
from opensprite_backend.workspaces import (
    UNASSIGNED_WORKSPACE_ID,
    JsonWorkspaceStore,
    WorkspaceCatalogService,
    WorkspaceError,
    WorkspaceFailure,
    WorkspaceMutationGate,
    WorkspaceRootPolicy,
)


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
        assert request.max_output_tokens == 8_192
        yield ModelTextDelta("真實流程回覆")
        yield ModelCompleted(ModelFinishReason.FINAL)


def service(
    tmp_path: Path,
    *,
    model: bool = True,
    connected: bool = True,
    with_notifier: bool = False,
):
    event_notifier = RunEventNotifier() if with_notifier else None
    paths = build_app_paths(tmp_path / ".opensprite")
    repository = SqliteConversationRepository(
        paths.database_file,
        event_notifier=event_notifier,
    )
    gate = WorkspaceMutationGate()
    workspaces = WorkspaceCatalogService(
        JsonWorkspaceStore(paths.workspace_settings_file),
        WorkspaceRootPolicy(
            data_root=paths.home,
            user_home=tmp_path / "home",
            install_root=tmp_path / "installed-app",
        ),
        usage_reader=repository,
        mutation_gate=gate,
    )
    settings = AiSettings(
        model=(
            ModelSelection(
                providerId="openrouter",
                modelId="openrouter/auto",
                contextBudget="auto",
                outputBudget="auto",
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
        capability_resolver=TestCapabilityResolver(),
    )
    manager = RunManager(repository, loop)
    chat = AgentChatService(
        repository,
        FixedSettings(settings),
        FixedConnections({"openrouter"} if connected else set()),
        manager,
        workspaces,
        gate,
        event_notifier=event_notifier,
        event_poll_seconds=0.001,
    )
    return chat, repository, manager, workspaces


@async_test
async def test_start_run_persists_then_executes_and_lists_real_data(
    tmp_path: Path,
) -> None:
    chat, repository, manager, _workspaces = service(tmp_path)

    accepted = await chat.start_run(
        conversation_id=None,
        workspace_id=UNASSIGNED_WORKSPACE_ID,
        client_request_id="e898796c-71e9-4eb5-aac1-7a6e9430a429",
        message="整理今天的工作",
    )
    completed = await manager.wait(accepted.run.id)

    assert completed is not None
    assert completed.status is RunStatus.COMPLETED
    assert completed.output_budget == "auto"
    conversations = await chat.list_conversations(
        workspace_id=UNASSIGNED_WORKSPACE_ID,
        limit=50,
        before=None,
    )
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
    chat, _repository, manager, _workspaces = service(tmp_path)
    request_id = "e898796c-71e9-4eb5-aac1-7a6e9430a429"

    first = await chat.start_run(
        conversation_id=None,
        workspace_id=UNASSIGNED_WORKSPACE_ID,
        client_request_id=request_id,
        message="hello",
    )
    replay = await chat.start_run(
        conversation_id=None,
        workspace_id=UNASSIGNED_WORKSPACE_ID,
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
        chat, _repository, _manager, _workspaces = service(
            tmp_path,
            model=model,
            connected=connected,
        )
        with pytest.raises(AgentChatError) as captured:
            await chat.start_run(
                conversation_id=None,
                workspace_id=UNASSIGNED_WORKSPACE_ID,
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
    chat, _repository, manager, _workspaces = service(tmp_path)
    accepted = await chat.start_run(
        conversation_id=None,
        workspace_id=UNASSIGNED_WORKSPACE_ID,
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
async def test_custom_workspace_is_resolved_persisted_and_movable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat, repository, manager, workspaces = service(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    catalog = await workspaces.create(
        name="Alpha",
        root_path=str(root),
        expected_revision=0,
    )
    workspace = next(
        item for item in catalog.workspaces if item.id == catalog.active_workspace_id
    )
    captured_workspaces = []
    original_start = manager.start

    async def capture_start(run_id, workspace_context):
        captured_workspaces.append(workspace_context)
        return await original_start(run_id, workspace_context)

    monkeypatch.setattr(manager, "start", capture_start)

    accepted = await chat.start_run(
        conversation_id=None,
        workspace_id=workspace.id,
        client_request_id="3ac641eb-03a5-4d9d-a50e-d2b0e2802ed1",
        message="workspace message",
    )
    renamed = await workspaces.update(
        workspace.id,
        name="Beta",
        root_path=str(root),
        expected_revision=workspace.revision,
    )
    await manager.wait(accepted.run.id)

    assert renamed.name == "Beta"
    assert len(captured_workspaces) == 1
    assert captured_workspaces[0].name == "Alpha"
    assert captured_workspaces[0].revision == workspace.revision
    assert captured_workspaces[0].root_path == workspace.root_path
    assert accepted.conversation.workspace_id == workspace.id
    assert accepted.run.workspace_id == workspace.id
    assert accepted.run.workspace_revision == workspace.revision
    assert accepted.run.workspace_name_snapshot == "Alpha"
    assert accepted.run.workspace_root_hash is not None
    assert str(root).encode("utf-8") not in repository.database_file.read_bytes()
    page = await chat.list_conversations(
        workspace_id=workspace.id,
        limit=50,
        before=None,
    )
    assert [item.id for item in page.items] == [accepted.conversation.id]

    moved = await chat.move_conversation(
        accepted.conversation.id,
        workspace_id=UNASSIGNED_WORKSPACE_ID,
        expected_revision=accepted.conversation.revision,
    )
    assert moved.workspace_id == UNASSIGNED_WORKSPACE_ID
    assert moved.revision == 2
    persisted_run = repository.get_run(accepted.run.id)
    assert persisted_run is not None
    assert persisted_run.workspace_id == workspace.id
    await chat.close()


@async_test
async def test_shared_workspace_gate_serializes_run_start_and_root_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat, repository, manager, workspaces = service(tmp_path)
    root = tmp_path / "project"
    replacement = tmp_path / "replacement"
    root.mkdir()
    replacement.mkdir()
    catalog = await workspaces.create(
        name="Alpha",
        root_path=str(root),
        expected_revision=0,
    )
    workspace = next(
        item for item in catalog.workspaces if item.id == catalog.active_workspace_id
    )
    entered = Event()
    release = Event()
    original_start_run = repository.start_run

    def blocking_start_run(**kwargs):
        entered.set()
        if not release.wait(timeout=2):
            raise AssertionError("run-start gate was not released")
        return original_start_run(**kwargs)

    monkeypatch.setattr(repository, "start_run", blocking_start_run)
    start_task = asyncio.create_task(
        chat.start_run(
            conversation_id=None,
            workspace_id=workspace.id,
            client_request_id="4ac641eb-03a5-4d9d-a50e-d2b0e2802ed1",
            message="serialized workspace message",
        )
    )
    assert await asyncio.to_thread(entered.wait, 1)
    update_task = asyncio.create_task(
        workspaces.update(
            workspace.id,
            name="Alpha",
            root_path=str(replacement),
            expected_revision=workspace.revision,
        )
    )
    await asyncio.sleep(0)
    assert update_task.done() is False
    release.set()

    accepted = await start_task
    with pytest.raises(WorkspaceError) as busy:
        await update_task

    assert busy.value.failure is WorkspaceFailure.WORKSPACE_BUSY
    await manager.wait(accepted.run.id)
    await chat.close()


@async_test
async def test_scheduled_start_uses_fixed_profile_and_disables_prompt_log(
    tmp_path: Path,
) -> None:
    chat, repository, manager, _workspaces = service(tmp_path)
    occurrence_id = "e898796c-71e9-4eb5-aac1-7a6e9430a430"
    profile = ExecutionProfile(
        "openrouter",
        "openrouter/fixed-model",
        "deep",
        "128k",
        "32k",
        "10",
    )

    accepted = await chat.start_scheduled_run(
        conversation_id=None,
        occurrence_id=occurrence_id,
        message="scheduled work",
        profile=profile,
    )
    completed = await manager.wait(accepted.run.id)

    assert completed is not None
    assert completed.source == "schedule"
    assert completed.occurrence_id == occurrence_id
    assert completed.model_id == "openrouter/fixed-model"
    assert completed.response_mode == "deep"
    assert completed.context_budget == "128k"
    assert completed.output_budget == "32k"
    assert completed.output_continuation == "10"
    assert completed.log_full_prompts is False
    assert repository.get_run(completed.id) == completed
    await chat.close()


@async_test
async def test_event_stream_waits_for_persisted_event_notification(
    tmp_path: Path,
) -> None:
    chat, repository, _manager, _workspaces = service(tmp_path, with_notifier=True)
    accepted = repository.start_run(
        conversation_id=None,
        client_request_id="e898796c-71e9-4eb5-aac1-7a6e9430a429",
        message="hello",
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
    )
    repository.mark_run_started(accepted.run.id)
    stream = chat.stream_events(accepted.run.id, after_sequence=1)
    next_event = asyncio.create_task(anext(stream))
    await asyncio.sleep(0.02)
    assert next_event.done() is False

    persisted = repository.append_run_event(
        accepted.run.id,
        RunEventType.MODEL_STARTED,
        {
            "providerId": "openrouter",
            "modelId": "openrouter/auto",
            "responseMode": "default",
            "maxOutputTokens": 8_192,
        },
    )

    assert await asyncio.wait_for(next_event, timeout=1) == persisted
    await stream.aclose()
    await chat.close()


@async_test
async def test_startup_interrupts_existing_non_terminal_runs(
    tmp_path: Path,
) -> None:
    chat, repository, _manager, _workspaces = service(tmp_path)
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
