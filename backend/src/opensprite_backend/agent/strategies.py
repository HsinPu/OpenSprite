"""Recovery decisions evaluated only after the host's fixed eligibility gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from opensprite_backend.conversations.models import OutputContinuation
from opensprite_backend.inference.models import ModelFinishReason


@dataclass(frozen=True, slots=True)
class ContextRetryState:
    phase: Literal["main", "continuation"]
    cause: Literal["provider_context_limit", "local_budget"]


@dataclass(frozen=True, slots=True)
class CompletionState:
    finish_reason: ModelFinishReason
    output_continuation: OutputContinuation


class ExecutionStrategy(Protocol):
    def allow_context_retry(self, state: ContextRetryState) -> bool: ...

    def allow_output_continuation(self, state: CompletionState) -> bool: ...


class StandardExecutionStrategy:
    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return True

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return True


class NoRecoveryExecutionStrategy:
    def allow_context_retry(self, state: ContextRetryState) -> bool:
        return False

    def allow_output_continuation(self, state: CompletionState) -> bool:
        return False
