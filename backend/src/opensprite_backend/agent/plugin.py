"""API v3 for one trusted, Run-local Agent Loop plugin.

The same instance coordinates Host operations and vetoes eligible recovery.
Model requests, credentials, transcripts, persistence and limits stay in core.
This in-process contract is not a security sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from opensprite_backend.conversations.models import CompletionReason, OutputContinuation
from opensprite_backend.inference.models import ModelFinishReason


@dataclass(frozen=True, slots=True)
class ModelTurn:
    text: str
    finish_reason: ModelFinishReason


@dataclass(frozen=True, slots=True)
class DriverResult:
    text: str
    completion_reason: CompletionReason


@dataclass(frozen=True, slots=True)
class ContextRetryState:
    phase: Literal["main", "continuation"]
    cause: Literal["provider_context_limit", "local_budget"]


@dataclass(frozen=True, slots=True)
class CompletionState:
    finish_reason: ModelFinishReason
    output_continuation: OutputContinuation


class ExecutionHost(Protocol):
    async def checkpoint(self) -> None: ...

    async def next_turn(self) -> ModelTurn: ...

    async def finish(self, turn: ModelTurn) -> DriverResult: ...


class AgentLoopPlugin(Protocol):
    async def execute(self, host: ExecutionHost) -> DriverResult: ...

    def allow_context_retry(self, state: ContextRetryState) -> bool: ...

    def allow_output_continuation(self, state: CompletionState) -> bool: ...


class AgentLoopPluginFactory(Protocol):
    api_version: int

    def create(self) -> AgentLoopPlugin: ...
