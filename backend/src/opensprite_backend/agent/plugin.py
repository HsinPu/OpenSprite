"""API v4: trusted Run-local Loops arrange bounded text operations.

The Host owns effects. A Loop owns context selection, recovery, continuation
and its sequence of draft/answer calls. This contract is not a Python sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from opensprite_backend.conversations.models import (
    CompletionReason, ConversationCompaction, Message, OutputContinuation,
    PublicRunError,
)
from opensprite_backend.inference.models import ModelFinishReason, ModelMessage
from .context.budget import ContextBudgetPlan


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_model_requests: int = 128
    max_compactions: int = 32
    max_duration_seconds: float = 600
    max_text_chars: int = 1_048_576


@dataclass(frozen=True, slots=True)
class RunContext:
    run_id: str
    conversation_id: str
    user_message_id: str
    provider_id: str
    model_id: str
    output_continuation: OutputContinuation
    budget: ContextBudgetPlan
    limits: ExecutionLimits
    plugin_id: str
    plugin_version: str


@dataclass(frozen=True, slots=True)
class ContextSpec:
    recent_messages: int = 1
    selection_tokens: int | None = None
    use_summary: bool = True
    summary_format: str = "opensprite.text.v1"
    history_ids: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class ContextResult:
    id: str
    messages: tuple[ModelMessage, ...]
    budget: ContextBudgetPlan
    history: tuple[Message, ...]
    summary: ConversationCompaction | None
    compaction_candidates: tuple[Message, ...]
    needs_compaction: bool
    estimated_input_tokens: int
    error: PublicRunError | None = None


@dataclass(frozen=True, slots=True)
class StepRequest:
    context: ContextResult
    label: str = "answer"
    channel: Literal["draft", "answer"] = "answer"
    messages: tuple[ModelMessage, ...] = ()
    instruction: str = ""
    max_output_tokens: int | None = None
    purpose: Literal["main", "continuation"] = "main"
    retry_of: StepResult | None = None


@dataclass(frozen=True, slots=True)
class StepResult:
    id: str
    text: str
    finish_reason: ModelFinishReason | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: PublicRunError | None = None


@dataclass(frozen=True, slots=True)
class CompactionSpec:
    context: ContextResult
    messages: tuple[Message, ...]
    instruction: str
    summary_format: str = "opensprite.text.v1"
    max_output_tokens: int = 2048
    reason: Literal["local_budget", "provider_context_limit"] = "local_budget"
    parent_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompactionResult:
    step: StepResult
    summary: ConversationCompaction | None


@dataclass(frozen=True, slots=True)
class FinalOutput:
    text: str = ""
    sources: tuple[StepResult, ...] = ()
    completion_reason: CompletionReason = CompletionReason.STOP
    error_step: StepResult | None = None
    context_error: ContextResult | None = None
    failure: Literal["context_limit_exceeded", "context_preparation_failed", "loop_failed"] | None = None


@dataclass(frozen=True, slots=True)
class RunResult:
    text: str
    completion_reason: CompletionReason
    error: PublicRunError | None = None


class ExecutionHost(Protocol):
    @property
    def run(self) -> RunContext: ...
    async def checkpoint(self) -> None: ...
    async def context(self, spec: ContextSpec = ContextSpec()) -> ContextResult: ...
    async def infer(self, request: StepRequest) -> StepResult: ...
    async def compact(self, spec: CompactionSpec) -> CompactionResult: ...
    async def finish(self, output: FinalOutput) -> RunResult: ...


class AgentLoopPlugin(Protocol):
    async def execute(self, host: ExecutionHost) -> RunResult: ...


class AgentLoopPluginFactory(Protocol):
    api_version: int
    def create(self) -> AgentLoopPlugin: ...
