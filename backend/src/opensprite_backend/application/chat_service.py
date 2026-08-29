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
from opensprite_backend.models import ErrorCode
from opensprite_backend.provider_connections import (
    ProviderConnectionError,
    ProviderConnections,
)


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
        event_poll_seconds: float = 0.05,
    ) -> None:
        if not 0.001 <= event_poll_seconds <= 5:
            raise ValueError("invalid event polling interval")
        self._repository = repository
        self._ai_settings = ai_settings
        self._provider_connections = provider_connections
        self._run_manager = run_manager
        self._event_poll_seconds = event_poll_seconds

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
                if provider.id == settings.model.provider_id
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
                provider_id=settings.model.provider_id,
                model_id=settings.model.model_id,
                response_mode=settings.responseMode.value,
                context_budget=settings.model.context_budget,
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
            if not events:
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
