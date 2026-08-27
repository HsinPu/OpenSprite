"""Typed FastAPI application factory for the local OpenSprite backend."""

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import Lifespan

from .api.ai_settings_routes import (
    ai_settings_error_response,
    router as ai_settings_router,
)
from .api.chat_models import chat_error_response
from .api.chat_routes import router as chat_router
from .api.provider_routes import (
    provider_error_response,
    router as provider_router,
)
from .application import (
    AgentChatError,
    AgentChatOperations,
    UnavailableAgentChat,
)
from .local_security import LocalRequestSecurityMiddleware
from .models import AiSettingsErrorCode, ErrorCode, HealthResponse
from .ai_settings import (
    AiSettingsOperations,
    SettingsStoreError,
    UnavailableAiSettings,
)
from .provider_connections import (
    ProviderConnectionError,
    ProviderConnections,
    UnavailableProviderConnections,
)

ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]


def create_app(
    provider_connections: ProviderConnections | None = None,
    *,
    ai_settings: AiSettingsOperations | None = None,
    agent_chat: AgentChatOperations | None = None,
    lifespan: Lifespan[FastAPI] | None = None,
    enforce_local_security: bool = False,
) -> FastAPI:
    """Create the ASGI app with an injectable provider-connection boundary."""

    app = FastAPI(
        title="OpenSprite local backend",
        version="0.1.0",
        description="Loopback-only local desktop service foundation.",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.provider_connections = (
        provider_connections
        if provider_connections is not None
        else UnavailableProviderConnections()
    )
    app.state.ai_settings = (
        ai_settings
        if ai_settings is not None
        else UnavailableAiSettings()
    )
    app.state.agent_chat = (
        agent_chat if agent_chat is not None else UnavailableAgentChat()
    )
    if enforce_local_security:
        app.add_middleware(
            LocalRequestSecurityMiddleware,
            rejection_response=lambda: provider_error_response(
                ErrorCode.INVALID_REQUEST
            ),
        )

    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return provider_error_response(ErrorCode.INVALID_REQUEST)

    async def provider_error_handler(
        request: Request,
        exc: ProviderConnectionError,
    ) -> JSONResponse:
        del request
        return provider_error_response(exc.code)

    async def settings_store_error_handler(
        request: Request,
        exc: SettingsStoreError,
    ) -> JSONResponse:
        del request, exc
        return ai_settings_error_response(
            AiSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE
        )

    async def agent_chat_error_handler(
        request: Request,
        exc: AgentChatError,
    ) -> JSONResponse:
        del request
        return chat_error_response(exc.code)

    async def internal_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        del request, exc
        return provider_error_response(ErrorCode.INTERNAL_ERROR)

    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_error_handler),
    )
    app.add_exception_handler(
        ProviderConnectionError,
        cast(ExceptionHandler, provider_error_handler),
    )
    app.add_exception_handler(
        SettingsStoreError,
        cast(ExceptionHandler, settings_store_error_handler),
    )
    app.add_exception_handler(
        AgentChatError,
        cast(ExceptionHandler, agent_chat_error_handler),
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

    app.include_router(ai_settings_router)
    app.include_router(provider_router)
    app.include_router(chat_router)
    return app
