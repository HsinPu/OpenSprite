"""Normalized model transcript and stream records used by the Agent loop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeAlias


ProviderId = Literal["openai", "anthropic", "openrouter"]
ResponseMode = Literal["default", "fast", "balanced", "deep"]
ModelRole = Literal["system", "user", "assistant", "tool"]
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class InferenceFailure(str, Enum):
    PROVIDER_NOT_CONNECTED = "provider_not_connected"
    INVALID_CREDENTIALS = "invalid_credentials"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"


class ModelFinishReason(str, Enum):
    FINAL = "final"
    TOOL_CALLS = "tool_calls"


@dataclass(frozen=True, slots=True)
class ModelToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]

    def __post_init__(self) -> None:
        if _NAME.fullmatch(self.name) is None:
            raise ValueError("invalid model tool name")
        if not self.description or len(self.description) > 1024:
            raise ValueError("invalid model tool description")
        if not isinstance(self.input_schema, dict):
            raise ValueError("invalid model tool schema")


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    call_id: str
    name: str
    arguments: dict[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, str) or not 1 <= len(self.call_id) <= 128:
            raise ValueError("invalid model tool call id")
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise ValueError("invalid model tool call name")
        if not isinstance(self.arguments, dict):
            raise ValueError("invalid model tool call arguments")
        encoded = json.dumps(
            self.arguments,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded) > 65536:
            raise ValueError("model tool call arguments are too large")


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: ModelRole
    content: str
    tool_calls: tuple[ModelToolCall, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant", "tool"}:
            raise ValueError("invalid model message role")
        if not isinstance(self.content, str) or len(self.content) > 1048576:
            raise ValueError("invalid model message content")
        if self.role in {"system", "user"}:
            if not self.content or self.tool_calls or self.tool_call_id or self.tool_name:
                raise ValueError("invalid plain model message")
        elif self.role == "assistant":
            if self.tool_call_id is not None or self.tool_name is not None:
                raise ValueError("invalid assistant tool metadata")
            if not self.content and not self.tool_calls:
                raise ValueError("assistant message must have content or tool calls")
        elif (
            not self.content
            or self.tool_calls
            or not self.tool_call_id
            or not self.tool_name
            or _NAME.fullmatch(self.tool_name) is None
        ):
            raise ValueError("invalid tool result message")


@dataclass(frozen=True, slots=True)
class ModelRequest:
    provider_id: ProviderId
    model_id: str
    response_mode: ResponseMode
    messages: tuple[ModelMessage, ...]
    tools: tuple[ModelToolDefinition, ...]

    def __post_init__(self) -> None:
        if self.provider_id not in {"openai", "anthropic", "openrouter"}:
            raise ValueError("invalid request provider")
        if not isinstance(self.model_id, str) or not 1 <= len(self.model_id) <= 256:
            raise ValueError("invalid request model")
        if self.response_mode not in {"default", "fast", "balanced", "deep"}:
            raise ValueError("invalid request response mode")
        if not self.messages or len(self.messages) > 256 or len(self.tools) > 64:
            raise ValueError("invalid request bounds")
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("duplicate request tool")


@dataclass(frozen=True, slots=True)
class ModelTextDelta:
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not 1 <= len(self.text) <= 16384:
            raise ValueError("invalid text delta")


@dataclass(frozen=True, slots=True)
class ModelUsage:
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError("invalid token usage")


@dataclass(frozen=True, slots=True)
class ModelCompleted:
    reason: ModelFinishReason

    def __post_init__(self) -> None:
        if not isinstance(self.reason, ModelFinishReason):
            raise ValueError("invalid finish reason")


ModelStreamEvent: TypeAlias = (
    ModelTextDelta | ModelToolCall | ModelUsage | ModelCompleted
)
