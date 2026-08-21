"""Consumer-visible models for the provider-connection HTTP boundary."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProviderId = Literal["openai", "anthropic", "openrouter"]


class ContractModel(BaseModel):
    """Base model that rejects contract fields not declared explicitly."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"


class ProviderStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    INVALID_CREDENTIALS = "invalid_credentials"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"


class ProviderSummary(ContractModel):
    id: ProviderId
    name: str
    connected: bool
    status: ProviderStatus
    credential_preview: str | None = Field(alias="credentialPreview")
    last_checked_at: datetime | None = Field(alias="lastCheckedAt")

    @field_validator("last_checked_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != timedelta(0)
        ):
            raise ValueError("lastCheckedAt must be a UTC timestamp")
        return value

    @model_validator(mode="after")
    def require_coherent_connection_state(self) -> "ProviderSummary":
        if not self.connected:
            if self.status is not ProviderStatus.DISCONNECTED:
                raise ValueError("a disconnected provider must have disconnected status")
            if self.credential_preview is not None or self.last_checked_at is not None:
                raise ValueError("a disconnected provider cannot expose connection metadata")
        elif self.status is ProviderStatus.DISCONNECTED:
            raise ValueError("a connected provider cannot have disconnected status")
        elif self.last_checked_at is None:
            raise ValueError("a connected provider must have a lastCheckedAt value")
        return self


class ProviderListResponse(ContractModel):
    providers: list[ProviderSummary] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def require_fixed_ordered_catalog(self) -> "ProviderListResponse":
        catalog = tuple((provider.id, provider.name) for provider in self.providers)
        if catalog != (
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("openrouter", "OpenRouter"),
        ):
            raise ValueError(
                "providers must be ordered as openai/OpenAI then "
                "anthropic/Anthropic then openrouter/OpenRouter"
            )
        return self


class OpenRouterModel(ContractModel):
    id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)


class OpenRouterModelListResponse(ContractModel):
    models: list[OpenRouterModel] = Field(min_length=1, max_length=1000)


class PutProviderConnectionRequest(ContractModel):
    apiKey: str = Field(min_length=1, max_length=4096)

    @field_validator("apiKey")
    @classmethod
    def reject_whitespace_only_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("apiKey must contain a non-whitespace character")
        return value


class ModelSelection(ContractModel):
    provider_id: ProviderId = Field(alias="providerId")
    model_id: str = Field(alias="modelId", min_length=1, max_length=256)

    @field_validator("model_id")
    @classmethod
    def reject_whitespace_only_model_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("modelId must contain a non-whitespace character")
        return value


class ResponseMode(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"


class AiSettings(ContractModel):
    model: ModelSelection | None
    responseMode: ResponseMode


class PutAiSettingsRequest(ContractModel):
    model: ModelSelection | None
    responseMode: ResponseMode


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    NOT_CONNECTED = "not_connected"
    INVALID_CREDENTIALS = "invalid_credentials"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class ErrorDetail(ContractModel):
    code: ErrorCode
    message: str
    retryable: bool


class ErrorEnvelope(ContractModel):
    error: ErrorDetail


class AiSettingsErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    NOT_CONNECTED = "not_connected"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"
    SETTINGS_STORE_UNAVAILABLE = "settings_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class AiSettingsErrorDetail(ContractModel):
    code: AiSettingsErrorCode
    message: str
    retryable: bool


class AiSettingsErrorEnvelope(ContractModel):
    error: AiSettingsErrorDetail
