"""Consumer-visible models for the provider-connection HTTP boundary."""

from datetime import datetime, timedelta
from enum import StrEnum
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, field_validator, model_validator

ProviderId = Literal["openai", "anthropic", "openrouter"]
InterfaceLocale = Literal["zh-TW", "en", "ja"]
TimeZoneSetting = Literal["system", "Asia/Taipei", "UTC"]
StartupView = Literal["new", "recent"]
SendBehavior = Literal["enter", "modifier-enter"]
ContextBudget = Literal["auto", "32k", "64k", "128k", "256k", "max"]
OutputBudget = Literal["auto", "8k", "16k", "32k", "64k", "max"]
ToolSourceValue = Literal["builtin", "mcp", "external"]
ToolEffectValue = Literal[
    "read_only",
    "local_write",
    "external_write",
    "destructive",
    "sensitive",
]
_TOOL_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
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


class AuthUnauthenticated(ContractModel):
    state: Literal["unauthenticated"] = "unauthenticated"


class AuthAuthenticated(ContractModel):
    state: Literal["authenticated"] = "authenticated"
    expiresAt: datetime


AuthStatus = Annotated[
    AuthSetupRequired | AuthUnauthenticated | AuthAuthenticated,
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


class ResponseMode(StrEnum):
    DEFAULT = "default"
    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"


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


class ToolSummary(ContractModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    source: ToolSourceValue
    effect: ToolEffectValue
    available: StrictBool


class ToolListResponse(ContractModel):
    items: list[ToolSummary] = Field(max_length=64)

    @field_validator("items")
    @classmethod
    def require_sorted_unique_items(
        cls,
        value: list[ToolSummary],
    ) -> list[ToolSummary]:
        ids = [item.id for item in value]
        if ids != sorted(set(ids)):
            raise ValueError("tool catalog must be sorted and unique")
        return value


def _validate_enabled_tool_ids(value: list[str]) -> list[str]:
    if len(set(value)) != len(value) or any(
        _TOOL_ID.fullmatch(item) is None for item in value
    ):
        raise ValueError("enabledTools must contain unique tool ids")
    return value


class ToolSettings(ContractModel):
    enabled: StrictBool
    enabledTools: list[str] = Field(max_length=64)

    @field_validator("enabledTools")
    @classmethod
    def validate_enabled_tools(cls, value: list[str]) -> list[str]:
        return _validate_enabled_tool_ids(value)


class PutToolSettingsRequest(ContractModel):
    enabled: StrictBool
    enabledTools: list[str] = Field(max_length=64)

    @field_validator("enabledTools")
    @classmethod
    def validate_enabled_tools(cls, value: list[str]) -> list[str]:
        return _validate_enabled_tool_ids(value)


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


class ToolSettingsErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    TOOL_NOT_FOUND = "tool_not_found"
    SETTINGS_STORE_UNAVAILABLE = "settings_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class ToolSettingsErrorDetail(ContractModel):
    code: ToolSettingsErrorCode
    message: str
    retryable: bool


class ToolSettingsErrorEnvelope(ContractModel):
    error: ToolSettingsErrorDetail


class McpServerStatus(StrEnum):
    DISABLED = "disabled"
    STOPPED = "stopped"
    STARTING = "starting"
    CONNECTED = "connected"
    ERROR = "error"
    STOPPING = "stopping"


class McpStdioTransport(ContractModel):
    type: Literal["stdio"] = "stdio"
    executable: str = Field(min_length=1, max_length=2048)
    arguments: list[str] = Field(max_length=64)
    workingDirectory: str | None = Field(default=None, max_length=2048)

    @field_validator("executable", "workingDirectory")
    @classmethod
    def reject_invalid_path_text(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in ("\x00", "\r", "\n")):
            raise ValueError("invalid path text")
        return value

    @field_validator("arguments")
    @classmethod
    def require_bounded_arguments(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 2048 or any(character in item for character in ("\x00", "\r", "\n")) for item in value):
            raise ValueError("invalid stdio argument")
        return value


class McpStreamableHttpTransport(ContractModel):
    type: Literal["streamable-http"] = "streamable-http"
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def reject_invalid_url_text(cls, value: str) -> str:
        if any(character in value for character in ("\x00", "\r", "\n")):
            raise ValueError("invalid MCP URL text")
        return value


McpTransport = Annotated[
    McpStdioTransport | McpStreamableHttpTransport,
    Field(discriminator="type"),
]


class McpNoAuthentication(ContractModel):
    type: Literal["none"] = "none"


class McpBearerAuthenticationInput(ContractModel):
    type: Literal["bearer-token"] = "bearer-token"
    token: SecretStr | None = Field(default=None, min_length=1, max_length=8192)

    @field_validator("token")
    @classmethod
    def reject_blank_token(cls, value: SecretStr | None) -> SecretStr | None:
        if (
            value is not None
            and _BEARER_TOKEN.fullmatch(value.get_secret_value()) is None
        ):
            raise ValueError("Bearer token has invalid characters")
        return value


McpAuthenticationInput = Annotated[
    McpNoAuthentication | McpBearerAuthenticationInput,
    Field(discriminator="type"),
]


class McpBearerAuthenticationSummary(ContractModel):
    type: Literal["bearer-token"] = "bearer-token"
    configured: StrictBool


McpAuthenticationSummary = Annotated[
    McpNoAuthentication | McpBearerAuthenticationSummary,
    Field(discriminator="type"),
]


class CreateMcpServerRequest(ContractModel):
    name: str = Field(min_length=1, max_length=80)
    transport: McpTransport
    authentication: McpAuthenticationInput = Field(
        default_factory=McpNoAuthentication
    )
    startOnLaunch: StrictBool = False

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must contain non-whitespace")
        return value

    @model_validator(mode="after")
    def require_new_bearer_token(self) -> "CreateMcpServerRequest":
        authentication = self.authentication
        if (
            isinstance(authentication, McpBearerAuthenticationInput)
            and authentication.token is None
        ):
            raise ValueError("Bearer token is required when creating a server")
        if (
            isinstance(self.transport, McpStdioTransport)
            and not isinstance(authentication, McpNoAuthentication)
        ):
            raise ValueError("stdio does not support HTTP authentication")
        return self


class PutMcpServerRequest(ContractModel):
    name: str = Field(min_length=1, max_length=80)
    transport: McpTransport
    authentication: McpAuthenticationInput = Field(
        default_factory=McpNoAuthentication
    )
    startOnLaunch: StrictBool = False

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must contain non-whitespace")
        return value

    @model_validator(mode="after")
    def restrict_authentication_to_http(self) -> "PutMcpServerRequest":
        if (
            isinstance(self.transport, McpStdioTransport)
            and not isinstance(self.authentication, McpNoAuthentication)
        ):
            raise ValueError("stdio does not support HTTP authentication")
        return self


class McpServerSummary(ContractModel):
    id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    name: str
    enabled: StrictBool
    startOnLaunch: StrictBool
    transport: McpTransport
    authentication: McpAuthenticationSummary
    status: McpServerStatus
    protocolVersion: str | None
    errorCode: str | None
    toolCount: int = Field(ge=0, le=128)
    unsupportedToolCount: int = Field(ge=0, le=128)


class McpServerListResponse(ContractModel):
    servers: list[McpServerSummary] = Field(max_length=32)


class McpToolAnnotations(ContractModel):
    readOnlyHint: StrictBool
    destructiveHint: StrictBool
    idempotentHint: StrictBool
    openWorldHint: StrictBool


class McpToolSummary(ContractModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    serverId: str
    originalName: str = Field(min_length=1, max_length=128)
    title: str | None = Field(default=None, max_length=256)
    description: str = Field(min_length=1, max_length=1024)
    supported: StrictBool
    unsupportedReason: Literal["unsupported_schema"] | None
    annotations: McpToolAnnotations


class McpToolListResponse(ContractModel):
    tools: list[McpToolSummary] = Field(max_length=128)


class McpErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    SERVER_DISABLED = "server_disabled"
    SERVER_NOT_RUNNING = "server_not_running"
    SERVER_START_FAILED = "server_start_failed"
    SERVER_STOP_FAILED = "server_stop_failed"
    SERVER_UNREACHABLE = "server_unreachable"
    SERVER_TIMEOUT = "server_timeout"
    TOOLS_NOT_SUPPORTED = "tools_not_supported"
    TOOL_CATALOG_INVALID = "tool_catalog_invalid"
    REMOTE_URL_BLOCKED = "remote_url_blocked"
    AUTHENTICATION_REQUIRED = "authentication_required"
    TLS_VERIFICATION_FAILED = "tls_verification_failed"
    REDIRECT_NOT_ALLOWED = "redirect_not_allowed"
    PROTOCOL_UNSUPPORTED = "protocol_unsupported"
    MCP_STORE_UNAVAILABLE = "mcp_store_unavailable"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class McpErrorDetail(ContractModel):
    code: McpErrorCode
    message: str
    retryable: bool


class McpErrorEnvelope(ContractModel):
    error: McpErrorDetail


class ToolApprovalDecision(StrEnum):
    ALLOW_ONCE = "allow_once"
    DENY = "deny"


class ToolApprovalDetail(ContractModel):
    id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    runId: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    conversationId: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    toolId: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    toolName: str
    serverId: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    arguments: dict[str, object]
    argumentHash: str = Field(pattern=r"^[0-9a-f]{64}$")
    createdAt: datetime
    expiresAt: datetime

    @model_validator(mode="after")
    def require_utc_expiry(self) -> "ToolApprovalDetail":
        if self.createdAt.tzinfo is None or self.createdAt.utcoffset() != timedelta(0) or self.expiresAt.tzinfo is None or self.expiresAt.utcoffset() != timedelta(0) or self.expiresAt <= self.createdAt:
            raise ValueError("approval timestamps must be ordered UTC values")
        return self


class PutToolApprovalDecisionRequest(ContractModel):
    decision: ToolApprovalDecision


class ToolApprovalDecisionResponse(ContractModel):
    id: str
    decision: ToolApprovalDecision


class ToolApprovalErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_ALREADY_DECIDED = "approval_already_decided"
    DATABASE_UNAVAILABLE = "database_unavailable"
    INTERNAL_ERROR = "internal_error"


class ToolApprovalErrorDetail(ContractModel):
    code: ToolApprovalErrorCode
    message: str
    retryable: bool


class ToolApprovalErrorEnvelope(ContractModel):
    error: ToolApprovalErrorDetail
