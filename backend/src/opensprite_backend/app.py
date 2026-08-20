"""Typed FastAPI application factory for the local OpenSprite backend."""

from collections.abc import Awaitable, Callable
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Path, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .models import (
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    HealthResponse,
    ProviderId,
    ProviderListResponse,
    ProviderSummary,
    PutProviderConnectionRequest,
)
from .provider_connections import (
    ProviderConnectionError,
    ProviderConnections,
    UnavailableProviderConnections,
)

SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"openai", "anthropic"})
ProviderPathId = Annotated[
    str,
    Path(
        description="Stable provider identifier.",
        json_schema_extra={"enum": ["openai", "anthropic"]},
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


def _error_response(code: ErrorCode) -> JSONResponse:
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


ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]


def create_app(
    provider_connections: ProviderConnections | None = None,
) -> FastAPI:
    """Create the ASGI app with an injectable provider-connection boundary."""

    app = FastAPI(
        title="OpenSprite local backend",
        version="0.1.0",
        description="Loopback-only local desktop service foundation.",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.provider_connections = (
        provider_connections
        if provider_connections is not None
        else UnavailableProviderConnections()
    )

    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(ErrorCode.INVALID_REQUEST)

    async def provider_error_handler(
        request: Request,
        exc: ProviderConnectionError,
    ) -> JSONResponse:
        del request
        return _error_response(exc.code)

    async def internal_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        del request, exc
        return _error_response(ErrorCode.INTERNAL_ERROR)

    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_error_handler),
    )
    app.add_exception_handler(
        ProviderConnectionError,
        cast(ExceptionHandler, provider_error_handler),
    )
    app.add_exception_handler(
        Exception,
        cast(ExceptionHandler, internal_error_handler),
    )

    @app.get(
        "/healthz",
        operation_id="getHealth",
        response_model=HealthResponse,
        tags=["health"],
    )
    async def get_health() -> HealthResponse:
        return HealthResponse()

    @app.get(
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

    @app.put(
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

    @app.post(
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

    @app.delete(
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

    return app
