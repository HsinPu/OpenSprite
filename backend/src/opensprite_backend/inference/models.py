"""Normalized model transcript and stream records used by the Agent loop."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeAlias


from opensprite_backend.provider_identity import ProviderId
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot, valid_provider_id
from opensprite_backend.response_modes import HistoricalResponseMode as ResponseMode, HISTORICAL_RESPONSE_MODES, ReasoningResolution
ModelRole = Literal["system", "user", "assistant"]


class InferenceFailure(str, Enum):
    PROVIDER_NOT_CONNECTED = "provider_not_connected"
    INVALID_CREDENTIALS = "invalid_credentials"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    CONTEXT_LIMIT_EXCEEDED = "context_limit_exceeded"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"


class ModelFinishReason(str, Enum):
    FINAL = "final"
    OUTPUT_LIMIT = "output_limit"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: ModelRole
    content: str
    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError("invalid model message role")
        if not isinstance(self.content, str) or not 1 <= len(self.content) <= 1048576:
            raise ValueError("invalid model message content")


@dataclass(frozen=True, slots=True)
class ModelRequest:
    provider_id: ProviderId
    model_id: str
    response_mode: ResponseMode
    messages: tuple[ModelMessage, ...]
    max_output_tokens: int = 8192
    provider_endpoint: ProviderEndpointSnapshot | None = None
    reasoning_resolution: ReasoningResolution | None = None

    def __post_init__(self) -> None:
        if not valid_provider_id(self.provider_id):
            raise ValueError("invalid request provider")
        if self.provider_endpoint is not None and self.provider_endpoint.provider_id != self.provider_id:
            raise ValueError("provider snapshot mismatch")
        if not isinstance(self.model_id, str) or not 1 <= len(self.model_id) <= 256:
            raise ValueError("invalid request model")
        if self.response_mode not in HISTORICAL_RESPONSE_MODES:
            raise ValueError("invalid request response mode")
        if self.reasoning_resolution is not None and self.reasoning_resolution.requested != self.response_mode:
            raise ValueError("reasoning resolution mismatch")
        if not self.messages or len(self.messages) > 256:
            raise ValueError("invalid request bounds")
        if (
            not isinstance(self.max_output_tokens, int)
            or isinstance(self.max_output_tokens, bool)
            or not 1 <= self.max_output_tokens <= 131_072
        ):
            raise ValueError("invalid request output bound")


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
    ModelTextDelta | ModelUsage | ModelCompleted
)
