"""Application orchestration between settings, Providers, Runs, and storage."""

from __future__ import annotations
from opensprite_backend.providers.catalog_models import BUILTIN_PROVIDER_IDS, ProviderEndpointSnapshot
from opensprite_backend.providers.catalog_store import CatalogError
from opensprite_backend.providers.custom_service import CustomProviderService

import asyncio
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Protocol

from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.agent.plugin_catalog import ExecutionPluginCatalog, ExecutionPluginError
from opensprite_backend.execution_settings import ExecutionSettingsOperations, ExecutionSettingsError
from opensprite_backend.ai_settings import AiSettingsOperations, SettingsStoreError
from opensprite_backend.models import ModelSelection
from opensprite_backend.conversations.models import (
    ConversationPage,
    ConversationSummary,
    MessagePage,
    RunEvent,
    RunSnapshot,
    RunStatus,
    StartRunResult,
    StoreFailure,
)
from opensprite_backend.conversations.repository import (
    ConversationRepository,
    ConversationStoreError,
)
from opensprite_backend.conversations.event_notifier import RunEventNotifier
from opensprite_backend.models import ErrorCode
from opensprite_backend.provider_connections import (
    ProviderConnectionError,
    ProviderConnections,
)
from opensprite_backend.workspaces import (
    DEFAULT_WORKSPACE_ID,
    WorkspaceError,
    WorkspaceFailure,
    WorkspaceMutationGate,
    WorkspaceResolver,
)


class ChatErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    NOT_FOUND = "not_found"
    RUN_BUSY = "run_busy"
    RUN_NOT_ACTIVE = "run_not_active"
    MODEL_NOT_SELECTED = "model_not_selected"
    PROVIDER_NOT_CONNECTED = "provider_not_connected"
    INVALID_CREDENTIALS = "invalid_credentials"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"
    SETTINGS_STORE_UNAVAILABLE = "settings_store_unavailable"
    DATABASE_UNAVAILABLE = "database_unavailable"
    AGENT_LIMIT_REACHED = "agent_limit_reached"
    CONTEXT_LIMIT_EXCEEDED = "context_limit_exceeded"
    CONTEXT_PREPARATION_FAILED = "context_preparation_failed"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    INTERNAL_ERROR = "internal_error"
    WORKSPACE_NOT_FOUND = "workspace_not_found"
    WORKSPACE_MISMATCH = "workspace_mismatch"
    WORKSPACE_STORE_UNAVAILABLE = "workspace_store_unavailable"
    REVISION_CONFLICT = "revision_conflict"


class AgentChatError(Exception):
    """Consumer-safe chat failure represented only by a fixed code."""

    def __init__(self, code: ChatErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class AgentChatOperations(Protocol):
    async def list_conversations(
        self,
        *,
        workspace_id: str,
        limit: int,
        before: str | None,
    ) -> ConversationPage: ...

    async def get_conversation(self, conversation_id: str) -> ConversationSummary: ...

    async def move_conversation(
        self,
        conversation_id: str,
        *,
        workspace_id: str,
        expected_revision: int,
    ) -> ConversationSummary: ...

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None,
    ) -> MessagePage: ...

    async def start_run(
        self,
        *,
        conversation_id: str | None,
        workspace_id: str,
        client_request_id: str,
        message: str,
    ) -> StartRunResult: ...

    async def get_run(self, run_id: str) -> RunSnapshot: ...

    async def event_history(self, run_id: str, *, after_sequence: int, limit: int) -> tuple[RunEvent, ...]: ...

    async def list_run_steps(self, run_id: str, *, after_sequence: int, limit: int): ...

    async def cancel_run(self, run_id: str) -> RunSnapshot: ...

    def stream_events(
        self,
        run_id: str,
        *,
        after_sequence: int,
    ) -> AsyncIterator[RunEvent]: ...


class UnavailableAgentChat:
    @staticmethod
    def _unavailable() -> AgentChatError:
        return AgentChatError(ChatErrorCode.DATABASE_UNAVAILABLE)

    async def list_conversations(
        self, *, workspace_id: str, limit: int, before: str | None
    ):
        del workspace_id, limit, before
        raise self._unavailable()

    async def get_conversation(self, conversation_id: str) -> ConversationSummary:
        del conversation_id
        raise self._unavailable()

    async def move_conversation(
        self,
        conversation_id: str,
        *,
        workspace_id: str,
        expected_revision: int,
    ) -> ConversationSummary:
        del conversation_id, workspace_id, expected_revision
        raise self._unavailable()

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None,
    ):
        del conversation_id, limit, before_sequence
        raise self._unavailable()

    async def start_run(
        self,
        *,
        conversation_id: str | None,
        workspace_id: str,
        client_request_id: str,
        message: str,
    ):
        del conversation_id, workspace_id, client_request_id, message
        raise self._unavailable()

    async def get_run(self, run_id: str):
        del run_id
        raise self._unavailable()

    async def event_history(self, run_id: str, *, after_sequence: int, limit: int):
        raise self._unavailable()

    async def list_run_steps(self, run_id: str, *, after_sequence: int, limit: int):
        raise self._unavailable()

    async def cancel_run(self, run_id: str):
        del run_id
        raise self._unavailable()

    async def stream_events(self, run_id: str, *, after_sequence: int):
        del run_id, after_sequence
        raise self._unavailable()
        if False:
            yield  # pragma: no cover


class AgentChatService:
    _TERMINAL = {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    }

    def __init__(
        self,
        repository: ConversationRepository,
        ai_settings: AiSettingsOperations,
        provider_connections: ProviderConnections,
        run_manager: RunManager,
        workspaces: WorkspaceResolver,
        workspace_mutation_gate: WorkspaceMutationGate,
        *,
        event_notifier: RunEventNotifier | None = None,
        custom_providers: CustomProviderService | None = None,
        execution_settings: ExecutionSettingsOperations | None = None,
        execution_plugins: ExecutionPluginCatalog | None = None,
        event_poll_seconds: float = 0.05,
        event_wait_seconds: float = 5.0,
    ) -> None:
        if not 0.001 <= event_poll_seconds <= 5:
            raise ValueError("invalid event polling interval")
        if not 0.1 <= event_wait_seconds <= 30:
            raise ValueError("invalid event wait interval")
        self._repository = repository
        self._ai_settings = ai_settings
        self._provider_connections = provider_connections
        self._run_manager = run_manager
        self._workspaces = workspaces
        self._custom_providers = custom_providers
        self._execution_settings = execution_settings
        self._execution_plugins = execution_plugins
        self._workspace_mutation_gate = workspace_mutation_gate
        self._event_poll_seconds = event_poll_seconds
        self._event_wait_seconds = event_wait_seconds
        self._event_notifier = event_notifier

    async def startup(self) -> tuple[str, ...]:
        try:
            return await asyncio.to_thread(
                self._repository.interrupt_incomplete_runs
            )
        except ConversationStoreError as error:
            raise _store_error(error) from error

    async def close(self) -> None:
        try:
            await self._run_manager.close()
        except ConversationStoreError as error:
            raise _store_error(error) from error

    async def list_conversations(
        self,
        *,
        workspace_id: str,
        limit: int,
        before: str | None,
    ) -> ConversationPage:
        try:
            self._workspaces.execution_context(workspace_id)
            return await asyncio.to_thread(
                self._repository.list_conversations,
                workspace_id=workspace_id,
                limit=limit,
                before=before,
            )
        except WorkspaceError as error:
            raise _workspace_error(error) from error
        except ConversationStoreError as error:
            raise _store_error(error) from error

    async def get_conversation(self, conversation_id: str):
        try:
            item = await asyncio.to_thread(
                self._repository.get_conversation,
                conversation_id,
            )
        except ConversationStoreError as error:
            raise _store_error(error) from error
        if item is None:
            raise AgentChatError(ChatErrorCode.NOT_FOUND)
        return item

    async def move_conversation(
        self,
        conversation_id: str,
        *,
        workspace_id: str,
        expected_revision: int,
    ):
        async with self._workspace_mutation_gate.hold():
            try:
                self._workspaces.execution_context(workspace_id)
                return await asyncio.to_thread(
                    self._repository.move_conversation,
                    conversation_id,
                    workspace_id=workspace_id,
                    expected_revision=expected_revision,
                )
            except WorkspaceError as error:
                raise _workspace_error(error) from error
            except ConversationStoreError as error:
                raise _store_error(error) from error

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None,
    ) -> MessagePage:
        try:
            conversation = await asyncio.to_thread(
                self._repository.get_conversation,
                conversation_id,
            )
            if conversation is None:
                raise AgentChatError(ChatErrorCode.NOT_FOUND)
            return await asyncio.to_thread(
                self._repository.list_messages,
                conversation_id,
                limit=limit,
                before_sequence=before_sequence,
            )
        except AgentChatError:
            raise
        except ConversationStoreError as error:
            raise _store_error(error) from error

    async def start_run(
        self,
        *,
        conversation_id: str | None,
        workspace_id: str,
        client_request_id: str,
        message: str,
    ) -> StartRunResult:
        replay = await self._find_run_request(
            conversation_id=conversation_id, workspace_id=workspace_id,
            client_request_id=client_request_id, message=message,
        )
        if replay is not None:
            return replay
        try:
            settings = await self._ai_settings.get()
        except SettingsStoreError as error:
            raise AgentChatError(ChatErrorCode.SETTINGS_STORE_UNAVAILABLE) from error
        if settings.model is None:
            raise AgentChatError(ChatErrorCode.MODEL_NOT_SELECTED)
        profile = settings.model
        return await self._start_configured_run(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            client_request_id=client_request_id,
            message=message,
            profile=profile,
            log_full_prompts=settings.logFullPrompts,
            response_mode=settings.responseMode.value,
        )


    async def wait_run(self, run_id: str) -> RunSnapshot | None:
        return await self._run_manager.wait(run_id)

    async def _find_run_request(
        self, *, conversation_id: str | None, workspace_id: str,
        client_request_id: str, message: str,
    ) -> StartRunResult | None:
        async with self._workspace_mutation_gate.hold():
            try:
                return await asyncio.to_thread(
                    self._repository.find_run_request,
                    conversation_id=conversation_id, workspace_id=workspace_id,
                    client_request_id=client_request_id, message=message,
                )
            except ConversationStoreError as error:
                raise _store_error(error) from error

    async def _start_configured_run(
        self,
        *,
        conversation_id: str | None,
        workspace_id: str,
        client_request_id: str,
        message: str,
        profile: ModelSelection,
        log_full_prompts: bool,
        response_mode: str,
    ) -> StartRunResult:
        is_custom = profile.provider_id not in BUILTIN_PROVIDER_IDS
        if not is_custom:
            try:
                providers = await self._provider_connections.list_providers()
            except ProviderConnectionError as error:
                code = (
                    ChatErrorCode.CREDENTIAL_STORE_UNAVAILABLE
                    if error.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
                    else ChatErrorCode.INTERNAL_ERROR
                )
                raise AgentChatError(code) from error
            selected = next((provider for provider in providers.providers if provider.id == profile.provider_id), None)
            if selected is None or not selected.connected:
                raise AgentChatError(ChatErrorCode.PROVIDER_NOT_CONNECTED)
        async with self._workspace_mutation_gate.hold():
            try:
                provider_endpoint = None
                if is_custom:
                    if self._custom_providers is None:
                        raise AgentChatError(ChatErrorCode.PROVIDER_NOT_CONNECTED)
                    try:
                        provider_endpoint = await asyncio.to_thread(self._custom_providers.execution_endpoint, profile.provider_id)
                    except CatalogError:
                        raise AgentChatError(ChatErrorCode.PROVIDER_NOT_CONNECTED) from None
                workspace = self._workspaces.execution_context(workspace_id)
                execution_binding = None
                if self._execution_settings is not None and self._execution_plugins is not None:
                    try:
                        selected_plugin = await asyncio.to_thread(self._execution_settings.selection)
                        execution_binding = await asyncio.to_thread(self._execution_plugins.resolve, selected_plugin)
                    except (ExecutionPluginError, ExecutionSettingsError):
                        raise AgentChatError(ChatErrorCode.SETTINGS_STORE_UNAVAILABLE) from None
                accepted = await asyncio.to_thread(
                    self._repository.start_run,
                    conversation_id=conversation_id,
                    client_request_id=client_request_id,
                    message=message,
                    provider_id=profile.provider_id,
                    model_id=profile.model_id,
                    response_mode=response_mode,
                    context_budget=profile.context_budget,
                    output_budget=profile.output_budget,
                    log_full_prompts=log_full_prompts,
                    workspace_id=workspace.id,
                    workspace_revision=workspace.revision,
                    workspace_name_snapshot=workspace.name,
                    workspace_root_hash=workspace.root_hash,
                    workspace_mount_manifest_hash=workspace.mount_manifest_hash,
                    execution_profile=execution_binding.profile() if execution_binding else None,
                )
            except WorkspaceError as error:
                raise _workspace_error(error) from error
            except ConversationStoreError as error:
                raise _store_error(error) from error
            if not accepted.replayed and accepted.run.status is RunStatus.QUEUED:
                await self._run_manager.start(
                    accepted.run.id, workspace, provider_endpoint,
                    execution_plugin=execution_binding,
                )
        return accepted

    async def get_run(self, run_id: str) -> RunSnapshot:
        try:
            run = await asyncio.to_thread(self._repository.get_run, run_id)
        except ConversationStoreError as error:
            raise _store_error(error) from error
        if run is None:
            raise AgentChatError(ChatErrorCode.NOT_FOUND)
        return run

    async def cancel_run(self, run_id: str) -> RunSnapshot:
        try:
            return await self._run_manager.cancel(run_id)
        except ConversationStoreError as error:
            raise _store_error(error) from error

    async def event_history(self, run_id: str, *, after_sequence: int, limit: int) -> tuple[RunEvent, ...]:
        if type(after_sequence) is not int or not 0 <= after_sequence <= 2**53 - 1 or type(limit) is not int or not 1 <= limit <= 100:
            raise AgentChatError(ChatErrorCode.INVALID_REQUEST)
        await self.get_run(run_id)
        try:
            return await asyncio.to_thread(self._repository.list_run_events, run_id,
                                           after_sequence=after_sequence, limit=limit + 1)
        except ConversationStoreError as error:
            raise _store_error(error) from error

    async def list_run_steps(self, run_id: str, *, after_sequence: int, limit: int):
        if type(after_sequence) is not int or not 0 <= after_sequence <= 2**53-1 or type(limit) is not int or not 1 <= limit <= 100:
            raise AgentChatError(ChatErrorCode.INVALID_REQUEST)
        await self.get_run(run_id)
        try:
            return await asyncio.to_thread(self._repository.list_run_steps, run_id,
                                           after_sequence=after_sequence, limit=limit + 1)
        except ConversationStoreError as error:
            raise _store_error(error) from error

    async def stream_events(
        self,
        run_id: str,
        *,
        after_sequence: int,
    ) -> AsyncIterator[RunEvent]:
        await self.get_run(run_id)
        current = after_sequence
        notifier_version = (
            None
            if self._event_notifier is None
            else self._event_notifier.version(run_id)
        )
        while True:
            try:
                events = await asyncio.to_thread(
                    self._repository.list_run_events,
                    run_id,
                    after_sequence=current,
                    limit=100,
                )
            except ConversationStoreError as error:
                raise _store_error(error) from error
            for event in events:
                current = event.sequence
                yield event
            run = await self.get_run(run_id)
            if run.status in self._TERMINAL and not events:
                return
            if not events and self._event_notifier is not None:
                notifier_version = await asyncio.to_thread(
                    self._event_notifier.wait,
                    run_id,
                    notifier_version,
                    self._event_wait_seconds,
                )
            elif not events:
                await asyncio.sleep(self._event_poll_seconds)


def _store_error(error: ConversationStoreError) -> AgentChatError:
    code = {
        StoreFailure.INVALID_REQUEST: ChatErrorCode.INVALID_REQUEST,
        StoreFailure.IDEMPOTENCY_CONFLICT: ChatErrorCode.IDEMPOTENCY_CONFLICT,
        StoreFailure.NOT_FOUND: ChatErrorCode.NOT_FOUND,
        StoreFailure.RUN_BUSY: ChatErrorCode.RUN_BUSY,
        StoreFailure.RUN_NOT_ACTIVE: ChatErrorCode.RUN_NOT_ACTIVE,
        StoreFailure.INVALID_STATE: ChatErrorCode.RUN_NOT_ACTIVE,
        StoreFailure.DATABASE_UNAVAILABLE: ChatErrorCode.DATABASE_UNAVAILABLE,
        StoreFailure.REVISION_CONFLICT: ChatErrorCode.REVISION_CONFLICT,
        StoreFailure.WORKSPACE_MISMATCH: ChatErrorCode.WORKSPACE_MISMATCH,

    }[error.failure]
    return AgentChatError(code)


def _workspace_error(error: WorkspaceError) -> AgentChatError:
    code = {
        WorkspaceFailure.NOT_FOUND: ChatErrorCode.WORKSPACE_NOT_FOUND,
        WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE: ChatErrorCode.WORKSPACE_STORE_UNAVAILABLE,
        WorkspaceFailure.WORKSPACE_BUSY: ChatErrorCode.RUN_BUSY,
        WorkspaceFailure.REVISION_CONFLICT: ChatErrorCode.REVISION_CONFLICT,
        WorkspaceFailure.INVALID_REQUEST: ChatErrorCode.INVALID_REQUEST,
        WorkspaceFailure.UNSAFE_ROOT: ChatErrorCode.INVALID_REQUEST,
        WorkspaceFailure.DUPLICATE_NAME: ChatErrorCode.INVALID_REQUEST,
        WorkspaceFailure.DUPLICATE_ROOT: ChatErrorCode.INVALID_REQUEST,
        WorkspaceFailure.WORKSPACE_NOT_EMPTY: ChatErrorCode.INVALID_REQUEST,
        WorkspaceFailure.INTERNAL_ERROR: ChatErrorCode.INTERNAL_ERROR,
    }[error.failure]
    return AgentChatError(code)
