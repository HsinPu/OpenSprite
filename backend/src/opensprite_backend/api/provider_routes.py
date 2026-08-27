"""Provider-connection HTTP routes and public error serialization."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Request, Response, status
from fastapi.responses import JSONResponse

from opensprite_backend.models import (
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    OpenRouterModelListResponse,
    ProviderId,
    ProviderListResponse,
    ProviderSummary,
    PutProviderConnectionRequest,
)
from opensprite_backend.provider_connections import (
    ProviderConnectionError,
    ProviderConnections,
)


router = APIRouter()

SUPPORTED_PROVIDERS: frozenset[str] = frozenset(
    {"openai", "anthropic", "openrouter"}
)
ProviderPathId = Annotated[
    str,
    Path(
        description="Stable provider identifier.",
        json_schema_extra={"enum": ["openai", "anthropic", "openrouter"]},
    ),
]

ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    ErrorCode.UNSUPPORTED_PROVIDER: status.HTTP_404_NOT_FOUND,
    ErrorCode.NOT_CONNECTED: status.HTTP_409_CONFLICT,
    ErrorCode.INVALID_CREDENTIALS: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.PROVIDER_RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.PROVIDER_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.CREDENTIAL_STORE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.PROVIDER_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}

PUBLIC_ERRORS: dict[ErrorCode, tuple[str, bool]] = {
    ErrorCode.INVALID_REQUEST: ("Request validation failed.", False),
    ErrorCode.UNSUPPORTED_PROVIDER: (
        "The requested provider is not supported.",
        False,
    ),
    ErrorCode.NOT_CONNECTED: ("The provider is not connected.", False),
    ErrorCode.INVALID_CREDENTIALS: (
        "The provider rejected the credential.",
        False,
    ),
    ErrorCode.PROVIDER_UNREACHABLE: (
        "The provider is temporarily unreachable.",
        True,
    ),
    ErrorCode.PROVIDER_TIMEOUT: (
        "The provider did not respond before the timeout.",
        True,
    ),
    ErrorCode.PROVIDER_RATE_LIMITED: (
        "The provider rate limit was reached.",
        True,
    ),
    ErrorCode.CREDENTIAL_STORE_UNAVAILABLE: (
        "Secure credential storage is unavailable.",
        True,
    ),
    ErrorCode.INTERNAL_ERROR: ("An internal error occurred.", False),
}

PROVIDER_LIST_ERROR_RESPONSES = {
    500: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
}
OPENROUTER_MODELS_ERROR_RESPONSES = {
    400: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
    500: {"model": ErrorEnvelope},
    502: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
    504: {"model": ErrorEnvelope},
}
PROVIDER_CONNECTION_ERROR_RESPONSES = {
    400: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
    500: {"model": ErrorEnvelope},
    502: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
    504: {"model": ErrorEnvelope},
}
PROVIDER_TEST_ERROR_RESPONSES = {
    **PROVIDER_CONNECTION_ERROR_RESPONSES,
    409: {"model": ErrorEnvelope},
}
PROVIDER_DELETE_ERROR_RESPONSES = {
    404: {"model": ErrorEnvelope},
    500: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
}


def provider_error_response(code: ErrorCode) -> JSONResponse:
    message, retryable = PUBLIC_ERRORS[code]
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, retryable=retryable)
    )
    return JSONResponse(
        status_code=ERROR_STATUS[code],
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _provider_id(value: str) -> ProviderId:
    if value not in SUPPORTED_PROVIDERS:
        raise ProviderConnectionError(ErrorCode.UNSUPPORTED_PROVIDER)
    return cast(ProviderId, value)


def _provider_connections(request: Request) -> ProviderConnections:
    return cast(ProviderConnections, request.app.state.provider_connections)


@router.get(
    "/api/providers",
    operation_id="listProviders",
    response_model=ProviderListResponse,
    responses=PROVIDER_LIST_ERROR_RESPONSES,
    tags=["provider-connections"],
)
async def list_providers(
    connections: ProviderConnections = Depends(_provider_connections),
) -> ProviderListResponse:
    return await connections.list_providers()


@router.post(
    "/api/providers/openrouter/models",
    operation_id="listOpenRouterModels",
    response_model=OpenRouterModelListResponse,
    responses=OPENROUTER_MODELS_ERROR_RESPONSES,
    tags=["provider-connections"],
)
async def list_openrouter_models(
    request: Request,
    connections: ProviderConnections = Depends(_provider_connections),
) -> OpenRouterModelListResponse:
    if await request.body():
        raise ProviderConnectionError(ErrorCode.INVALID_REQUEST)
    return await connections.list_openrouter_models()


@router.put(
    "/api/providers/{provider_id}/connection",
    operation_id="putProviderConnection",
    response_model=ProviderSummary,
    responses=PROVIDER_CONNECTION_ERROR_RESPONSES,
    tags=["provider-connections"],
)
async def put_provider_connection(
    provider_id: ProviderPathId,
    payload: PutProviderConnectionRequest,
    connections: ProviderConnections = Depends(_provider_connections),
) -> ProviderSummary:
    return await connections.connect(
        _provider_id(provider_id),
        payload.apiKey,
    )


@router.post(
    "/api/providers/{provider_id}/connection/test",
    operation_id="testProviderConnection",
    response_model=ProviderSummary,
    responses=PROVIDER_TEST_ERROR_RESPONSES,
    tags=["provider-connections"],
)
async def test_provider_connection(
    provider_id: ProviderPathId,
    request: Request,
    connections: ProviderConnections = Depends(_provider_connections),
) -> ProviderSummary:
    if await request.body():
        raise ProviderConnectionError(ErrorCode.INVALID_REQUEST)
    return await connections.test(_provider_id(provider_id))


@router.delete(
    "/api/providers/{provider_id}/connection",
    operation_id="deleteProviderConnection",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=PROVIDER_DELETE_ERROR_RESPONSES,
    tags=["provider-connections"],
)
async def delete_provider_connection(
    provider_id: ProviderPathId,
    connections: ProviderConnections = Depends(_provider_connections),
) -> Response:
    await connections.disconnect(_provider_id(provider_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
