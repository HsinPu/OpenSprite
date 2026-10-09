"""API v5: trusted Run-local Loops compose inputs; the Host owns effects.

The Host owns effects. A Loop owns context selection, recovery, continuation
and its sequence of draft/answer calls. This contract is not a Python sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from opensprite_backend.conversations.models import (
    CompletionReason, ConversationCompaction, Message, ContextBudget, OutputBudget,
    PublicRunError,
)
from opensprite_backend.inference.models import ModelFinishReason, ModelMessage


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_model_requests: int = 128
    max_compactions: int = 32
    max_duration_seconds: float = 600
    max_text_chars: int = 1_048_576


@dataclass(frozen=True, slots=True)
class ModelLimits:
    context_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class RunContext:
    run_id: str
    conversation_id: str
    user_message_id: str
    provider_id: str
    model_id: str
    context_budget: str
    output_budget: str
    model_limits: ModelLimits
    system_prompt: str
    limits: ExecutionLimits
    plugin_id: str
    plugin_version: str


@dataclass(frozen=True, slots=True)
class ContextReadRequest:
    before_sequence: int | None = None
    after_sequence: int | None = None
    limit: int = 100
    summary_format: str | None = "opensprite.text.v1"


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    id: str
    current_user: Message
    history: tuple[Message, ...]
    summary: ConversationCompaction | None
    next_before_sequence: int | None = None
    next_after_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class InputSource:
    """Bind an input position to owned raw data or an earlier inference step."""
    message_index: int
    snapshot: ContextSnapshot | None = None
    message_ids: tuple[str, ...] = ()
    summary_id: str | None = None
    steps: tuple[StepResult, ...] = ()


@dataclass(frozen=True, slots=True)
class SummarySource:
    snapshots: tuple[ContextSnapshot, ...]
    message_ids: tuple[str, ...]
    summary_format: str = "opensprite.text.v1"
    previous_summary_id: str | None = None
    reason: Literal["local_budget", "provider_context_limit"] = "local_budget"
    estimated_before_tokens: int = 0


@dataclass(frozen=True, slots=True)
class StepRequest:
    messages: tuple[ModelMessage, ...]
    max_output_tokens: int
    sources: tuple[InputSource, ...] = ()
    label: str = "answer"
    channel: Literal["draft", "answer"] = "answer"
    purpose: Literal["main", "continuation", "compaction"] = "main"
    retry_of: StepResult | None = None
    input_limit_tokens: int | None = None
    summary_source: SummarySource | None = None
    parent_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class StepResult:
    id: str
    text: str
    finish_reason: ModelFinishReason | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: PublicRunError | None = None


@dataclass(frozen=True, slots=True)
class SummaryWriteRequest:
    step: StepResult
    text: str


@dataclass(frozen=True, slots=True)
class FinalOutput:
    text: str = ""
    sources: tuple[StepResult, ...] = ()
    completion_reason: CompletionReason = CompletionReason.STOP
    error_step: StepResult | None = None
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
    async def read_context(self, request: ContextReadRequest = ContextReadRequest()) -> ContextSnapshot: ...
    async def estimate_input(self, messages: tuple[ModelMessage, ...]) -> int: ...
    async def infer(self, request: StepRequest) -> StepResult: ...
    async def save_summary(self, request: SummaryWriteRequest) -> ConversationCompaction: ...
    async def finish(self, output: FinalOutput) -> RunResult: ...


class AgentLoopPlugin(Protocol):
    async def execute(self, host: ExecutionHost) -> RunResult: ...


class AgentLoopPluginFactory(Protocol):
    api_version: int
    def create(self) -> AgentLoopPlugin: ...
