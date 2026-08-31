"""Production composition for the secured loopback ASGI runtime."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
import logging
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
from .conversations import SqliteConversationRepository
from .conversation_settings import (
    ConversationSettingsOperations,
    UnavailableConversationSettings,
    create_conversation_settings_service,
)
from .inference import ModelGateway
from .model_capability_resolver import ProviderModelCapabilityResolver
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
from .tools import ReadOnlyToolPolicy, ToolRegistry


class LocalProviderRuntime(Protocol):
    connections: ProviderConnections
    model_gateway: ModelGateway

    async def aclose(self) -> None: ...


class LocalSystemRuntime(LocalProviderRuntime, Protocol):
    ai_settings: AiSettingsOperations
    general_settings: GeneralSettingsOperations
    conversation_settings: ConversationSettingsOperations
    agent_chat: AgentChatOperations

    async def astart(self) -> None: ...


RuntimeFactory = Callable[[], LocalSystemRuntime]


class _SystemRuntime:
    def __init__(
        self,
        provider_runtime: LocalProviderRuntime,
        ai_settings: AiSettingsOperations,
        general_settings: GeneralSettingsOperations,
        conversation_settings: ConversationSettingsOperations,
        agent_chat: AgentChatService,
    ) -> None:
        self._provider_runtime = provider_runtime
        self.connections = provider_runtime.connections
        self.ai_settings = ai_settings
        self.general_settings = general_settings
        self.conversation_settings = conversation_settings
        self.agent_chat = agent_chat

    async def astart(self) -> None:
        provider_starter = getattr(self._provider_runtime, "astart", None)
        if provider_starter is not None:
            await provider_starter()
        await self.agent_chat.startup()

    async def aclose(self) -> None:
        try:
            await self.agent_chat.close()
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
    repository = SqliteConversationRepository(paths.database_file)
    agent_loop = AgentLoop(
        repository=repository,
        gateway=provider_runtime.model_gateway,
        tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
        capability_resolver=ProviderModelCapabilityResolver(
            provider_runtime.connections
        ),
        system_prompt_provider=create_system_prompt_provider(
            paths,
            general_settings,
        ),
        prompt_log_writer=FilePromptLogWriter(paths),
    )
    agent_chat = AgentChatService(
        repository,
        ai_settings,
        provider_runtime.connections,
        RunManager(repository, agent_loop),
    )
    return _SystemRuntime(
        provider_runtime,
        ai_settings,
        general_settings,
        conversation_settings,
        agent_chat,
    )


def create_system_app(
    *,
    app_paths: AppPaths | None = None,
    runtime_factory: RuntimeFactory | None = None,
) -> FastAPI:
    """Create an offline secured app with one fresh runtime per lifespan."""

    entry_lock = Lock()
    paths = app_paths if app_paths is not None else build_app_paths()
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
            app.state.agent_chat = UnavailableAgentChat()
            runtime = factory()
            starter = getattr(runtime, "astart", None)
            if starter is not None:
                await starter()
            app.state.provider_connections = runtime.connections
            app.state.ai_settings = runtime.ai_settings
            app.state.general_settings = runtime.general_settings
            app.state.conversation_settings = runtime.conversation_settings
            app.state.agent_chat = getattr(
                runtime,
                "agent_chat",
                UnavailableAgentChat(),
            )
            yield
        finally:
            app.state.provider_connections = UnavailableProviderConnections()
            app.state.ai_settings = UnavailableAiSettings()
            app.state.general_settings = UnavailableGeneralSettings()
            app.state.conversation_settings = UnavailableConversationSettings()
            app.state.agent_chat = UnavailableAgentChat()
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
    )
