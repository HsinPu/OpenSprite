"""Interface consumed by the Agent and HTTP layers, independent of SQLite."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from opensprite_backend.workspaces import WorkspaceAvailability

from .models import (
    CompletedRun,
    CompletionReason,
    ContextBudget,
    ConversationCompaction,
    ConversationPage,
    ConversationSummary,
    Message,
    MessagePage,
    OutputBudget,
    OutputContinuation,
    ProviderId,
    PublicRunError,
    ResponseMode,
    RunSource,
    RunEvent,
    RunEventType,
    RunSnapshot,
    StartRunResult,
    StoreFailure,
    UNASSIGNED_WORKSPACE_ID,
    UNASSIGNED_WORKSPACE_NAME,
)


class ConversationStoreError(Exception):
    """Fail-closed persistence error without implementation details."""

    def __init__(self, failure: StoreFailure) -> None:
        self.failure = failure
        super().__init__(failure.value)


class ConversationRepository(Protocol):
    def list_conversations(
        self,
        *,
        workspace_id: str = UNASSIGNED_WORKSPACE_ID,
        limit: int,
        before: str | None,
    ) -> ConversationPage: ...

    def get_conversation(
        self,
        conversation_id: str,
    ) -> ConversationSummary | None: ...

    def move_conversation(
        self,
        conversation_id: str,
        *,
        workspace_id: str,
        expected_revision: int,
    ) -> ConversationSummary: ...

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None,
    ) -> MessagePage: ...

    def list_messages_after(
        self,
        conversation_id: str,
        *,
        after_sequence: int,
        limit: int,
    ) -> tuple[Message, ...]: ...

    def get_run(self, run_id: str) -> RunSnapshot | None: ...

    def start_run(
        self,
        *,
        conversation_id: str | None,
        client_request_id: str,
        message: str,
        provider_id: ProviderId,
        model_id: str,
        response_mode: ResponseMode,
        context_budget: ContextBudget = "auto",
        output_budget: OutputBudget = "auto",
        output_continuation: OutputContinuation = "5",
        log_full_prompts: bool = False,
        source: RunSource = "user",
        occurrence_id: str | None = None,
        workspace_id: str = UNASSIGNED_WORKSPACE_ID,
        workspace_revision: int = 1,
        workspace_name_snapshot: str = UNASSIGNED_WORKSPACE_NAME,
        workspace_root_hash: str | None = None,
    ) -> StartRunResult: ...

    def get_latest_compaction(
        self,
        conversation_id: str,
    ) -> ConversationCompaction | None: ...

    def append_compaction(
        self,
        *,
        conversation_id: str,
        covers_through_sequence: int,
        summary: str,
        source_hash: str,
        provider_id: ProviderId,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> ConversationCompaction: ...

    def mark_run_started(
        self,
        run_id: str,
        workspace_availability: WorkspaceAvailability | None = None,
    ) -> RunSnapshot: ...

    def append_run_event(
        self,
        run_id: str,
        event_type: RunEventType,
        data: Mapping[str, object],
    ) -> RunEvent: ...

    def append_assistant_delta(self, run_id: str, text: str) -> RunEvent: ...

    def complete_run(
        self,
        run_id: str,
        assistant_text: str,
        completion_reason: CompletionReason = CompletionReason.STOP,
    ) -> CompletedRun: ...

    def fail_run(self, run_id: str, error: PublicRunError) -> RunSnapshot: ...

    def request_cancel(self, run_id: str) -> RunSnapshot: ...

    def mark_run_cancelled(self, run_id: str) -> RunSnapshot: ...

    def interrupt_incomplete_runs(self) -> tuple[str, ...]: ...

    def list_run_events(
        self,
        run_id: str,
        *,
        after_sequence: int,
        limit: int,
    ) -> tuple[RunEvent, ...]: ...
