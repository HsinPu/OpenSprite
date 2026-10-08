"""Consumer-visible models for the provider-connection HTTP boundary."""

from datetime import datetime, timedelta
from enum import StrEnum
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, field_validator, model_validator

from opensprite_backend.provider_identity import ProviderId
from .response_modes import ResponseMode
InterfaceLocale = Literal["zh-TW", "en", "ja"]
TimeZoneSetting = Literal["system", "Asia/Taipei", "UTC"]
StartupView = Literal["new", "recent"]
SendBehavior = Literal["enter", "modifier-enter"]
ContextBudget = Literal["auto", "32k", "64k", "128k", "256k", "max"]
OutputBudget = Literal["auto", "8k", "16k", "32k", "64k", "max"]
_BEARER_TOKEN = re.compile(r"^[A-Za-z0-9\-._~+/]+=*$")


class ContractModel(BaseModel):
    """Base model that rejects contract fields not declared explicitly."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"


class AuthSetupRequired(ContractModel):
    state: Literal["setup_required"] = "setup_required"


class AuthTrustedLocal(ContractModel):
    state: Literal["trusted_local"] = "trusted_local"


class AuthUnauthenticated(ContractModel):
    state: Literal["unauthenticated"] = "unauthenticated"


class AuthAuthenticated(ContractModel):
    state: Literal["authenticated"] = "authenticated"
    expiresAt: datetime


AuthStatus = Annotated[
    AuthTrustedLocal | AuthSetupRequired | AuthUnauthenticated | AuthAuthenticated,
    Field(discriminator="state"),
]


class AuthErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_CREDENTIALS = "invalid_credentials"
    SETUP_REQUIRED = "setup_required"
    SETUP_UNAVAILABLE = "setup_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_REQUIRED = "authentication_required"
    ACCESS_STORE_UNAVAILABLE = "access_store_unavailable"
    AUTHENTICATION_NOT_ENABLED = "authentication_not_enabled"
    INTERNAL_ERROR = "internal_error"


class AuthErrorDetail(ContractModel):
    code: AuthErrorCode
    message: str
    retryable: StrictBool


class AuthErrorEnvelope(ContractModel):
    error: AuthErrorDetail


class AuthSetupRequest(ContractModel):
    bootstrapToken: SecretStr = Field(min_length=32, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=128)


class AuthLoginRequest(ContractModel):
    password: SecretStr = Field(min_length=1, max_length=128)


class AuthPasswordChangeRequest(ContractModel):
    currentPassword: SecretStr = Field(min_length=1, max_length=128)
    newPassword: SecretStr = Field(min_length=1, max_length=128)


class LocalPathPickRequest(ContractModel):
    kind: Literal["executable", "directory"]


class LocalPathPickResponse(ContractModel):
    path: str = Field(min_length=1, max_length=32768)


LocalPathErrorCode = Literal[
    "invalid_request",
    "invalid_selection",
    "picker_busy",
    "picker_unavailable",
    "internal_error",
]


class LocalPathErrorDetail(ContractModel):
    code: LocalPathErrorCode
    message: str
    retryable: StrictBool


class LocalPathErrorEnvelope(ContractModel):
    error: LocalPathErrorDetail


class AppInfo(ContractModel):
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    revision: str = Field(pattern=r"^(?:[0-9a-f]{7,40}|development|unknown)$")
    buildType: Literal["development", "installed"]
    dirty: StrictBool
    installedAt: datetime | None


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
    providers: list[ProviderSummary] = Field(min_length=3)

    @model_validator(mode="after")
    def require_fixed_ordered_catalog(self) -> "ProviderListResponse":
        catalog = tuple((provider.id, provider.name) for provider in self.providers)
        if catalog[:3] != (
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("openrouter", "OpenRouter"),
        ):
            raise ValueError(
                "providers must be ordered as openai/OpenAI then "
                "anthropic/Anthropic then openrouter/OpenRouter"
            )
        if len({provider.id for provider in self.providers}) != len(self.providers):
            raise ValueError("duplicate provider id")
        return self


class OpenRouterModel(ContractModel):
    reasoning_efforts: tuple[str, ...] | None = Field(default=None, exclude=True)
    id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    context_window_tokens: int = Field(
        alias="contextWindowTokens",
        ge=1,
        le=4_000_000,
    )
    max_output_tokens: int | None = Field(
        alias="maxOutputTokens",
        default=None,
        ge=1,
        le=4_000_000,
    )

    @model_validator(mode="after")
    def require_output_within_context(self) -> "OpenRouterModel":
        if (
            self.max_output_tokens is not None
            and self.max_output_tokens > self.context_window_tokens
        ):
            raise ValueError("maxOutputTokens must fit within contextWindowTokens")
        return self


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
    context_budget: ContextBudget = Field(alias="contextBudget")
    output_budget: OutputBudget = Field(alias="outputBudget")

    @field_validator("model_id")
    @classmethod
    def reject_whitespace_only_model_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("modelId must contain a non-whitespace character")
        return value


class OutputContinuation(StrEnum):
    OFF = "off"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FIVE = "5"
    TEN = "10"
    TWENTY = "20"
    FIFTY = "50"
    UNLIMITED = "unlimited"


class ResponseDelivery(StrEnum):
    STREAM = "stream"
    COMPLETE = "complete"


class AiSettings(ContractModel):
    model: ModelSelection | None
    responseMode: ResponseMode
    outputContinuation: OutputContinuation = OutputContinuation.FIVE
    responseDelivery: ResponseDelivery = ResponseDelivery.STREAM
    logFullPrompts: StrictBool = False


class PutAiSettingsRequest(ContractModel):
    model: ModelSelection | None
    responseMode: ResponseMode
    outputContinuation: OutputContinuation
    responseDelivery: ResponseDelivery
    logFullPrompts: StrictBool


class GeneralSettings(ContractModel):
    locale: InterfaceLocale
    timeZone: TimeZoneSetting


class PutGeneralSettingsRequest(ContractModel):
    locale: InterfaceLocale
    timeZone: TimeZoneSetting


class ConversationSettings(ContractModel):
    startupView: StartupView
    sendBehavior: SendBehavior
    autoScroll: StrictBool
    executionPanelDefaultExpanded: StrictBool


class PutConversationSettingsRequest(ContractModel):
    startupView: StartupView
    sendBehavior: SendBehavior
    autoScroll: StrictBool
    executionPanelDefaultExpanded: StrictBool


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


class GeneralSettingsErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    SETTINGS_STORE_UNAVAILABLE = "settings_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class GeneralSettingsErrorDetail(ContractModel):
    code: GeneralSettingsErrorCode
    message: str
    retryable: bool


class GeneralSettingsErrorEnvelope(ContractModel):
    error: GeneralSettingsErrorDetail


class ConversationSettingsErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    SETTINGS_STORE_UNAVAILABLE = "settings_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class ConversationSettingsErrorDetail(ContractModel):
    code: ConversationSettingsErrorCode
    message: str
    retryable: bool


class ConversationSettingsErrorEnvelope(ContractModel):
    error: ConversationSettingsErrorDetail
