"""Production composition for the secured loopback ASGI runtime."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from threading import Lock
from typing import Protocol

from fastapi import FastAPI

from .agent import AgentLoop, RunManager
from .application import (
    AgentChatOperations,
    AgentChatService,
    UnavailableAgentChat,
)
from .app import create_app
from .app_paths import AppPaths, build_app_paths
from .build_info import load_app_info
from .runtime_logging import RuntimeLoggingSession, configure_runtime_logging
from .prompt_logging import FilePromptLogWriter
from .ai_settings import (
    AiSettingsOperations,
    UnavailableAiSettings,
    create_ai_settings_service,
)
from .conversations import RunEventNotifier, SqliteConversationRepository
from .credentials import CredentialStore
from .conversation_settings import (
    ConversationSettingsOperations,
    UnavailableConversationSettings,
    create_conversation_settings_service,
)
from .inference import ModelGateway
from .model_capability_resolver import ProviderModelCapabilityResolver
from .local_paths import create_local_path_picker
from .mcp import (
    McpConnections,
    UnavailableMcpConnections,
    create_mcp_connection_manager,
)
from .authentication import AccessMode, JsonAccessPolicyStore, UnavailableLocalAuthentication, create_local_authentication
from .authentication.store import AccessStoreError
from .general_settings import (
    GeneralSettingsOperations,
    UnavailableGeneralSettings,
    create_general_settings_service,
)
from .provider_connections import (
    ProviderConnections,
    UnavailableProviderConnections,
)
from .provider_runtime import create_provider_runtime
from .system_prompt import create_system_prompt_provider
from .tool_settings import (
    ToolSettingsOperations,
    UnavailableToolSettings,
    create_tool_settings_service,
)
from .tools import create_production_tool_registry
from .tools.approval import (
    ToolApprovalManager,
    ToolApprovalOperations,
    UnavailableToolApprovals,
)
from .tools.receipts import FileToolReceiptWriter
from .schedules.coordinator import ScheduleCoordinator
from .schedules.service import ScheduleOperations, ScheduleService, UnavailableSchedules
from .schedules.sqlite_repository import SqliteScheduleRepository
from .workspaces import (
    JsonWorkspaceStore,
    UnavailableWorkspaces,
    WorkspaceCatalogService,
    WorkspaceMutationGate,
    WorkspaceOperations,
    WorkspaceRootPolicy,
)


class LocalProviderRuntime(Protocol):
    connections: ProviderConnections
    model_gateway: ModelGateway
    credential_store: CredentialStore

    async def aclose(self) -> None: ...


class LocalSystemRuntime(LocalProviderRuntime, Protocol):
    ai_settings: AiSettingsOperations
    general_settings: GeneralSettingsOperations
    conversation_settings: ConversationSettingsOperations
    tool_settings: ToolSettingsOperations
    mcp_connections: McpConnections
    tool_approvals: ToolApprovalOperations
    agent_chat: AgentChatOperations
    schedules: ScheduleOperations
    workspaces: WorkspaceOperations

    async def astart(self) -> None: ...


RuntimeFactory = Callable[[], LocalSystemRuntime]


class _SystemRuntime:
    def __init__(
        self,
        provider_runtime: LocalProviderRuntime,
        ai_settings: AiSettingsOperations,
        general_settings: GeneralSettingsOperations,
        conversation_settings: ConversationSettingsOperations,
        tool_settings: ToolSettingsOperations,
        mcp_connections: McpConnections,
        tool_approvals: ToolApprovalOperations,
        workspaces: WorkspaceCatalogService,
        agent_chat: AgentChatService,
        schedules: ScheduleService,
        schedule_coordinator: ScheduleCoordinator,
    ) -> None:
        self._provider_runtime = provider_runtime
        self.connections = provider_runtime.connections
        self.ai_settings = ai_settings
        self.general_settings = general_settings
        self.conversation_settings = conversation_settings
        self.tool_settings = tool_settings
        self.mcp_connections = mcp_connections
        self.tool_approvals = tool_approvals
        self.workspaces = workspaces
        self.agent_chat = agent_chat
        self.schedules = schedules
        self._schedule_coordinator = schedule_coordinator

    async def astart(self) -> None:
        provider_starter = getattr(self._provider_runtime, "astart", None)
        if provider_starter is not None:
            await provider_starter()
        await self.mcp_connections.startup()
        await self.agent_chat.startup()
        await self._schedule_coordinator.start()

    async def aclose(self) -> None:
        try:
            await self._schedule_coordinator.close()
        finally:
            try:
                await self.agent_chat.close()
            finally:
                try:
                    await self.mcp_connections.close()
                finally:
                    await self._provider_runtime.aclose()


def create_system_runtime(
    *,
    app_paths: AppPaths | None = None,
) -> LocalSystemRuntime:
    """Compose providers and settings from one local OpenSprite root."""

    paths = app_paths if app_paths is not None else build_app_paths()
    provider_runtime = create_provider_runtime(app_paths=paths)
    ai_settings = create_ai_settings_service(
        paths,
        provider_runtime.connections,
    )
    general_settings = create_general_settings_service(paths)
    conversation_settings = create_conversation_settings_service(paths)
    event_notifier = RunEventNotifier()
    repository = SqliteConversationRepository(
        paths.database_file,
        event_notifier=event_notifier,
    )
    workspace_mutation_gate = WorkspaceMutationGate()
    workspaces = WorkspaceCatalogService(
        JsonWorkspaceStore(paths.workspace_settings_file),
        WorkspaceRootPolicy(
            data_root=paths.home,
            user_home=paths.user_home,
            install_root=Path(__file__).resolve().parents[3],
        ),
        usage_reader=repository,
        mutation_gate=workspace_mutation_gate,
    )
    tool_approvals = ToolApprovalManager(repository)
    tool_registry = create_production_tool_registry(
        tool_approvals,
        FileToolReceiptWriter(paths),
    )
    tool_settings = create_tool_settings_service(paths, tool_registry)
    mcp_connections = create_mcp_connection_manager(
        paths,
        credential_store=provider_runtime.credential_store,
    )
    agent_loop = AgentLoop(
        repository=repository,
        gateway=provider_runtime.model_gateway,
        tools=tool_registry,
        tool_availability=tool_settings,
        dynamic_tools=mcp_connections,
        capability_resolver=ProviderModelCapabilityResolver(
            provider_runtime.connections,
            operation_locks=provider_runtime.operation_locks,
        ),
        system_prompt_provider=create_system_prompt_provider(
            paths,
            general_settings,
        ),
        prompt_log_writer=FilePromptLogWriter(paths),
    )
    run_manager = RunManager(repository, agent_loop)
    agent_chat = AgentChatService(
        repository,
        ai_settings,
        provider_runtime.connections,
        run_manager,
        workspaces,
        workspace_mutation_gate,
        event_notifier=event_notifier,
    )
    schedule_repository = SqliteScheduleRepository(paths.database_file)
    schedule_coordinator = ScheduleCoordinator(schedule_repository, agent_chat)
    schedules = ScheduleService(
        schedule_repository,
        workspaces=workspaces,
        workspace_mutation_gate=workspace_mutation_gate,
        on_change=schedule_coordinator.wake,
    )
    return _SystemRuntime(
        provider_runtime,
        ai_settings,
        general_settings,
        conversation_settings,
        tool_settings,
        mcp_connections,
        tool_approvals,
        workspaces,
        agent_chat,
        schedules,
        schedule_coordinator,
    )


def create_system_app(
    *,
    app_paths: AppPaths | None = None,
    runtime_factory: RuntimeFactory | None = None,
    enforce_authentication: bool = True,
) -> FastAPI:
    """Create an offline secured app with one fresh runtime per lifespan."""

    entry_lock = Lock()
    paths = app_paths if app_paths is not None else build_app_paths()
    try:
        access_mode = JsonAccessPolicyStore(paths.access_policy_file).get().mode
        local_authentication = create_local_authentication(paths, access_mode=access_mode)
    except AccessStoreError:
        access_mode = AccessMode.PASSWORD_REQUIRED
        local_authentication = UnavailableLocalAuthentication()
    factory = runtime_factory
    if factory is None:
        factory = lambda: create_system_runtime(app_paths=paths)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not entry_lock.acquire(blocking=False):
            raise RuntimeError(
                "OpenSprite runtime lifespan is already active."
            )
        runtime: LocalSystemRuntime | None = None
        logging_session: RuntimeLoggingSession | None = None
        try:
            logging_session = configure_runtime_logging(paths)
            info = load_app_info()
            logging.getLogger("opensprite.runtime").info(
                "runtime started version=%s revision=%s dirty=%s",
                info.version,
                info.revision,
                info.dirty,
            )
            app.state.provider_connections = UnavailableProviderConnections()
            app.state.ai_settings = UnavailableAiSettings()
            app.state.general_settings = UnavailableGeneralSettings()
            app.state.conversation_settings = UnavailableConversationSettings()
            app.state.tool_settings = UnavailableToolSettings()
            app.state.mcp_connections = UnavailableMcpConnections()
            app.state.tool_approvals = UnavailableToolApprovals()
            app.state.agent_chat = UnavailableAgentChat()
            app.state.schedules = UnavailableSchedules()
            app.state.workspaces = UnavailableWorkspaces()
            runtime = factory()
            starter = getattr(runtime, "astart", None)
            if starter is not None:
                await starter()
            app.state.provider_connections = runtime.connections
            app.state.ai_settings = runtime.ai_settings
            app.state.general_settings = runtime.general_settings
            app.state.conversation_settings = runtime.conversation_settings
            app.state.tool_settings = getattr(
                runtime,
                "tool_settings",
                UnavailableToolSettings(),
            )
            app.state.mcp_connections = getattr(
                runtime,
                "mcp_connections",
                UnavailableMcpConnections(),
            )
            app.state.tool_approvals = getattr(
                runtime,
                "tool_approvals",
                UnavailableToolApprovals(),
            )
            app.state.agent_chat = getattr(
                runtime,
                "agent_chat",
                UnavailableAgentChat(),
            )
            app.state.schedules = getattr(
                runtime,
                "schedules",
                UnavailableSchedules(),
            )
            app.state.workspaces = getattr(
                runtime,
                "workspaces",
                UnavailableWorkspaces(),
            )
            yield
        finally:
            app.state.provider_connections = UnavailableProviderConnections()
            app.state.ai_settings = UnavailableAiSettings()
            app.state.general_settings = UnavailableGeneralSettings()
            app.state.conversation_settings = UnavailableConversationSettings()
            app.state.tool_settings = UnavailableToolSettings()
            app.state.mcp_connections = UnavailableMcpConnections()
            app.state.tool_approvals = UnavailableToolApprovals()
            app.state.agent_chat = UnavailableAgentChat()
            app.state.schedules = UnavailableSchedules()
            app.state.workspaces = UnavailableWorkspaces()
            try:
                if runtime is not None:
                    await runtime.aclose()
            finally:
                if logging_session is not None:
                    logging.getLogger("opensprite.runtime").info("runtime stopped")
                    logging_session.close()
                entry_lock.release()

    return create_app(
        lifespan=lifespan,
        enforce_local_security=True,
        local_path_picker=create_local_path_picker(),
        local_authentication=local_authentication,
        enforce_authentication=enforce_authentication and access_mode is AccessMode.PASSWORD_REQUIRED,
    )
