"""Stable v5 data exposed through agent.plugin, independent of storage/transport."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

ContextBudget = Literal["auto", "32k", "64k", "128k", "256k", "max"]
OutputBudget = Literal["auto", "8k", "16k", "32k", "64k", "max"]
MessageRole = Literal["user", "assistant"]
ModelRole = Literal["system", "user", "assistant"]


class CompletionReason(str, Enum):
    STOP = "stop"
    OUTPUT_LIMIT = "output_limit"
    CONTEXT_LIMIT = "context_limit"


class ModelFinishReason(str, Enum):
    FINAL = "final"
    OUTPUT_LIMIT = "output_limit"


@dataclass(frozen=True, slots=True)
class PublicRunError:
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    conversation_id: str
    run_id: str
    role: MessageRole
    content: str
    sequence: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationCompaction:
    id: str
    conversation_id: str
    covers_through_sequence: int
    summary: str
    summary_version: int
    source_hash: str
    provider_id: str
    model_id: str
    input_tokens: int
    output_tokens: int
    created_at: datetime
    producer_plugin_id: str = "legacy"
    producer_plugin_version: str = "unknown"
    summary_format: str = "opensprite.text.v1"
    source_step_id: str | None = None
    source_first_sequence: int | None = None
    previous_summary_id: str | None = None


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: ModelRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError("invalid model message role")
        if not isinstance(self.content, str) or not 1 <= len(self.content) <= 1048576:
            raise ValueError("invalid model message content")
