"""Application orchestration between settings, Providers, Runs, and storage."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Protocol

from opensprite_backend.agent.run_manager import RunManager
from opensprite_backend.ai_settings import AiSettingsOperations, SettingsStoreError
from opensprite_backend.conversations.models import (
    ConversationPage,
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
from opensprite_backend.schedules.models import ExecutionProfile


class ChatErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
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
    TOOL_FAILURE = "tool_failure"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    INTERNAL_ERROR = "internal_error"


class AgentChatError(Exception):
    """Consumer-safe chat failure represented only by a fixed code."""

    def __init__(self, code: ChatErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class AgentChatOperations(Protocol):
    async def list_conversations(
        self,
        *,
        limit: int,
        before: str | None,
    ) -> ConversationPage: ...

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
        client_request_id: str,
        message: str,
    ) -> StartRunResult: ...

    async def get_run(self, run_id: str) -> RunSnapshot: ...

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

    async def list_conversations(self, *, limit: int, before: str | None):
        del limit, before
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
        client_request_id: str,
        message: str,
    ):
        del conversation_id, client_request_id, message
        raise self._unavailable()

    async def get_run(self, run_id: str):
        del run_id
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
        *,
        event_notifier: RunEventNotifier | None = None,
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
        limit: int,
        before: str | None,
    ) -> ConversationPage:
        try:
            return await asyncio.to_thread(
                self._repository.list_conversations,
                limit=limit,
                before=before,
            )
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
        client_request_id: str,
        message: str,
    ) -> StartRunResult:
        try:
            settings = await self._ai_settings.get()
        except SettingsStoreError as error:
            raise AgentChatError(ChatErrorCode.SETTINGS_STORE_UNAVAILABLE) from error
        if settings.model is None:
            raise AgentChatError(ChatErrorCode.MODEL_NOT_SELECTED)
        profile = ExecutionProfile(
            settings.model.provider_id,
            settings.model.model_id,
            settings.responseMode.value,
            settings.model.context_budget,
            settings.model.output_budget,
            settings.outputContinuation.value,
        )
        return await self._start_configured_run(
            conversation_id=conversation_id,
            client_request_id=client_request_id,
            message=message,
            profile=profile,
            source="user",
            occurrence_id=None,
            log_full_prompts=settings.logFullPrompts,
        )

    async def start_scheduled_run(
        self,
        *,
        conversation_id: str | None,
        occurrence_id: str,
        message: str,
        profile: ExecutionProfile,
    ) -> StartRunResult:
        return await self._start_configured_run(
            conversation_id=conversation_id,
            client_request_id=occurrence_id,
            message=message,
            profile=profile,
            source="schedule",
            occurrence_id=occurrence_id,
            log_full_prompts=False,
        )

    async def wait_run(self, run_id: str) -> RunSnapshot | None:
        return await self._run_manager.wait(run_id)

    async def _start_configured_run(
        self,
        *,
        conversation_id: str | None,
        client_request_id: str,
        message: str,
        profile: ExecutionProfile,
        source: str,
        occurrence_id: str | None,
        log_full_prompts: bool,
    ) -> StartRunResult:
        try:
            providers = await self._provider_connections.list_providers()
        except ProviderConnectionError as error:
            code = (
                ChatErrorCode.CREDENTIAL_STORE_UNAVAILABLE
                if error.code is ErrorCode.CREDENTIAL_STORE_UNAVAILABLE
                else ChatErrorCode.INTERNAL_ERROR
            )
            raise AgentChatError(code) from error
        selected = next(
            (
                provider
                for provider in providers.providers
                if provider.id == profile.provider_id
            ),
            None,
        )
        if selected is None or not selected.connected:
            raise AgentChatError(ChatErrorCode.PROVIDER_NOT_CONNECTED)
        try:
            accepted = await asyncio.to_thread(
                self._repository.start_run,
                conversation_id=conversation_id,
                client_request_id=client_request_id,
                message=message,
                provider_id=profile.provider_id,
                model_id=profile.model_id,
                response_mode=profile.response_mode,
                context_budget=profile.context_budget,
                output_budget=profile.output_budget,
                output_continuation=profile.output_continuation,
                log_full_prompts=log_full_prompts,
                source=source,
                occurrence_id=occurrence_id,
            )
        except ConversationStoreError as error:
            raise _store_error(error) from error
        if accepted.run.status is RunStatus.QUEUED:
            await self._run_manager.start(accepted.run.id)
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
        StoreFailure.IDEMPOTENCY_CONFLICT: ChatErrorCode.INVALID_REQUEST,
        StoreFailure.NOT_FOUND: ChatErrorCode.NOT_FOUND,
        StoreFailure.RUN_BUSY: ChatErrorCode.RUN_BUSY,
        StoreFailure.RUN_NOT_ACTIVE: ChatErrorCode.RUN_NOT_ACTIVE,
        StoreFailure.INVALID_STATE: ChatErrorCode.RUN_NOT_ACTIVE,
        StoreFailure.DATABASE_UNAVAILABLE: ChatErrorCode.DATABASE_UNAVAILABLE,
    }[error.failure]
    return AgentChatError(code)
