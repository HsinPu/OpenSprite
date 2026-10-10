"""Interface consumed by the Agent and HTTP layers, independent of SQLite."""

from __future__ import annotations
from opensprite_backend.response_modes import ReasoningResolution

from collections.abc import Mapping
from typing import Protocol

from opensprite_backend.workspaces.models import EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH, WorkspaceAvailability

from .run_limits import RunLimitEvidence
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
    RunEvent,
    RunEventType,
    RunSnapshot,
    RunStep,
    StartRunResult,
    StoreFailure,
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
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
        workspace_id: str = DEFAULT_WORKSPACE_ID,
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

    def get_message(self, message_id: str) -> Message | None: ...

    def get_run(self, run_id: str) -> RunSnapshot | None: ...

    def find_run_request(
        self, *, conversation_id: str | None, workspace_id: str,
        client_request_id: str, message: str,
    ) -> StartRunResult | None: ...

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
        log_full_prompts: bool = False,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        workspace_revision: int = 1,
        workspace_name_snapshot: str = DEFAULT_WORKSPACE_NAME,
        workspace_root_hash: str | None = None,
        workspace_mount_manifest_hash: str = EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH,
        execution_profile: Mapping[str, object] | None = None,
    ) -> StartRunResult: ...

    def get_latest_compaction(
        self,
        conversation_id: str,
        *, summary_format: str = "opensprite.text.v1", before_sequence: int | None = None,
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
        producer_plugin_id: str = "legacy",
        producer_plugin_version: str = "unknown",
        summary_format: str = "opensprite.text.v1",
        compaction_id: str | None = None,
        source_step_id: str | None = None,
        source_first_sequence: int | None = None,
        expected_previous_summary_id: str | None = None,
        run_id: str | None = None,
    ) -> ConversationCompaction: ...

    def set_reasoning_resolution(self, run_id: str, resolution: ReasoningResolution) -> RunSnapshot: ...

    def mark_run_started(
        self,
        run_id: str,
        workspace_availability: WorkspaceAvailability | None = None,
        workspace_mounts: tuple[Mapping[str, object], ...] = (),
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

    def fail_run(self, run_id: str, error: PublicRunError, *, limit: RunLimitEvidence | None = None) -> RunSnapshot: ...

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

    def start_step(self, run_id: str, *, label: str, channel: str, retry_of: str | None = None) -> RunStep: ...

    def append_step_delta(self, step_id: str, text: str) -> None: ...

    def finish_step(self, step_id: str, *, status: str, finish_reason: str | None = None,
                    error_code: str | None = None, input_tokens: int | None = None,
                    output_tokens: int | None = None) -> RunStep: ...

    def list_run_steps(self, run_id: str, *, after_sequence: int = 0, limit: int = 100) -> tuple[RunStep, ...]: ...
