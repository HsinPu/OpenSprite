"""Typed FastAPI application factory for the local OpenSprite backend."""

from collections.abc import Awaitable, Callable
import logging
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
from .api.conversation_settings_routes import (
    conversation_settings_error_response,
    router as conversation_settings_router,
)
from .api.app_info_routes import router as app_info_router
from .api.general_settings_routes import (
    general_settings_error_response,
    router as general_settings_router,
)
from .api.local_path_routes import (
    local_path_error_response,
    router as local_path_router,
)
from .api.provider_routes import (
    provider_error_response,
    router as provider_router,
)
from .api.mcp_routes import mcp_error_response, router as mcp_router
from .api.tool_approval_routes import (
    router as tool_approval_router,
    tool_approval_error_response,
)
from .api.tool_settings_routes import (
    router as tool_settings_router,
    tool_settings_error_response,
)
from .application import (
    AgentChatError,
    AgentChatOperations,
    UnavailableAgentChat,
)
from .local_security import LocalRequestSecurityMiddleware
from .local_paths import (
    LocalPathPickerError,
    LocalPathPickerOperations,
    UnavailableLocalPathPicker,
)
from .models import (
    AppInfo,
    AiSettingsErrorCode,
    ConversationSettingsErrorCode,
    ErrorCode,
    GeneralSettingsErrorCode,
    HealthResponse,
    McpErrorCode,
    ToolSettingsErrorCode,
    ToolApprovalErrorCode,
)
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
from .general_settings import (
    GeneralSettingsOperations,
    GeneralSettingsStoreError,
    UnavailableGeneralSettings,
)
from .build_info import load_app_info
from .conversation_settings import (
    ConversationSettingsOperations,
    ConversationSettingsStoreError,
    UnavailableConversationSettings,
)
from .tool_settings import (
    ToolNotFoundError,
    ToolSettingsOperations,
    ToolSettingsStoreError,
    UnavailableToolSettings,
)
from .mcp import McpConnections, UnavailableMcpConnections
from .mcp.config import McpConfigStoreError
from .mcp.manager import McpConnectionError
from .tools.approval import (
    ToolApprovalError,
    ToolApprovalOperations,
    UnavailableToolApprovals,
)

ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]
_LOGGER = logging.getLogger("opensprite.runtime")


def create_app(
    provider_connections: ProviderConnections | None = None,
    *,
    ai_settings: AiSettingsOperations | None = None,
    general_settings: GeneralSettingsOperations | None = None,
    conversation_settings: ConversationSettingsOperations | None = None,
    tool_settings: ToolSettingsOperations | None = None,
    mcp_connections: McpConnections | None = None,
    local_path_picker: LocalPathPickerOperations | None = None,
    tool_approvals: ToolApprovalOperations | None = None,
    agent_chat: AgentChatOperations | None = None,
    app_info: AppInfo | None = None,
    lifespan: Lifespan[FastAPI] | None = None,
    enforce_local_security: bool = False,
) -> FastAPI:
    """Create the ASGI app with an injectable provider-connection boundary."""

    resolved_app_info = app_info if app_info is not None else load_app_info()
    app = FastAPI(
        title="OpenSprite local backend",
        version=resolved_app_info.version,
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
    app.state.general_settings = (
        general_settings
        if general_settings is not None
        else UnavailableGeneralSettings()
    )
    app.state.app_info = resolved_app_info
    app.state.conversation_settings = (
        conversation_settings
        if conversation_settings is not None
        else UnavailableConversationSettings()
    )
    app.state.tool_settings = (
        tool_settings if tool_settings is not None else UnavailableToolSettings()
    )
    app.state.mcp_connections = (
        mcp_connections if mcp_connections is not None else UnavailableMcpConnections()
    )
    app.state.local_path_picker = (
        local_path_picker
        if local_path_picker is not None
        else UnavailableLocalPathPicker()
    )
    app.state.tool_approvals = (
        tool_approvals if tool_approvals is not None else UnavailableToolApprovals()
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
        del exc
        if request.url.path == "/api/local-paths/pick":
            return local_path_error_response("invalid_request")
        return provider_error_response(ErrorCode.INVALID_REQUEST)

    async def local_path_error_handler(
        request: Request,
        exc: LocalPathPickerError,
    ) -> JSONResponse:
        del request
        return local_path_error_response(exc.code)

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

    async def general_settings_store_error_handler(
        request: Request,
        exc: GeneralSettingsStoreError,
    ) -> JSONResponse:
        del request, exc
        return general_settings_error_response(
            GeneralSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE
        )

    async def conversation_settings_store_error_handler(
        request: Request,
        exc: ConversationSettingsStoreError,
    ) -> JSONResponse:
        del request, exc
        return conversation_settings_error_response(
            ConversationSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE
        )

    async def tool_settings_store_error_handler(
        request: Request,
        exc: ToolSettingsStoreError,
    ) -> JSONResponse:
        del request, exc
        return tool_settings_error_response(
            ToolSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE
        )

    async def tool_not_found_error_handler(
        request: Request,
        exc: ToolNotFoundError,
    ) -> JSONResponse:
        del request, exc
        return tool_settings_error_response(ToolSettingsErrorCode.TOOL_NOT_FOUND)

    async def mcp_config_store_error_handler(
        request: Request,
        exc: McpConfigStoreError,
    ) -> JSONResponse:
        del request, exc
        return mcp_error_response(McpErrorCode.MCP_STORE_UNAVAILABLE)

    async def mcp_connection_error_handler(
        request: Request,
        exc: McpConnectionError,
    ) -> JSONResponse:
        del request
        return mcp_error_response(exc.code, retryable=exc.retryable)

    async def tool_approval_error_handler(
        request: Request,
        exc: ToolApprovalError,
    ) -> JSONResponse:
        del request
        return tool_approval_error_response(exc.code)

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
        _LOGGER.exception("request failed path=%s", request.url.path, exc_info=exc)
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
        LocalPathPickerError,
        cast(ExceptionHandler, local_path_error_handler),
    )
    app.add_exception_handler(
        SettingsStoreError,
        cast(ExceptionHandler, settings_store_error_handler),
    )
    app.add_exception_handler(
        GeneralSettingsStoreError,
        cast(ExceptionHandler, general_settings_store_error_handler),
    )
    app.add_exception_handler(
        ConversationSettingsStoreError,
        cast(ExceptionHandler, conversation_settings_store_error_handler),
    )
    app.add_exception_handler(
        ToolSettingsStoreError,
        cast(ExceptionHandler, tool_settings_store_error_handler),
    )
    app.add_exception_handler(
        ToolNotFoundError,
        cast(ExceptionHandler, tool_not_found_error_handler),
    )
    app.add_exception_handler(
        McpConfigStoreError,
        cast(ExceptionHandler, mcp_config_store_error_handler),
    )
    app.add_exception_handler(
        McpConnectionError,
        cast(ExceptionHandler, mcp_connection_error_handler),
    )
    app.add_exception_handler(
        ToolApprovalError,
        cast(ExceptionHandler, tool_approval_error_handler),
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

    app.include_router(app_info_router)
    app.include_router(ai_settings_router)
    app.include_router(general_settings_router)
    app.include_router(conversation_settings_router)
    app.include_router(tool_settings_router)
    app.include_router(mcp_router)
    app.include_router(local_path_router)
    app.include_router(tool_approval_router)
    app.include_router(provider_router)
    app.include_router(chat_router)
    return app
