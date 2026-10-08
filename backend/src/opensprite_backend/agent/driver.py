"""Small orchestration contract for trusted, in-process Agent drivers.

Drivers choose the sequence of host operations. The host owns model requests,
transcripts and Run persistence; this API is not a sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from opensprite_backend.conversations.models import CompletionReason
from opensprite_backend.inference.models import ModelFinishReason


@dataclass(frozen=True, slots=True)
class ModelTurn:
    text: str
    finish_reason: ModelFinishReason


@dataclass(frozen=True, slots=True)
class DriverResult:
    text: str
    completion_reason: CompletionReason


class ExecutionHost(Protocol):
    async def checkpoint(self) -> None: ...

    async def next_turn(self) -> ModelTurn: ...

    async def finish(self, turn: ModelTurn) -> DriverResult: ...


class AgentDriver(Protocol):
    async def execute(self, host: ExecutionHost) -> DriverResult: ...


class AgentDriverFactory(Protocol):
    api_version: int

    def create(self) -> AgentDriver: ...
