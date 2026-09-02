"""Tool catalog and tool-settings HTTP routes."""

from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from opensprite_backend.models import (
    PutToolSettingsRequest,
    ToolListResponse,
    ToolSettings,
    ToolSettingsErrorCode,
    ToolSettingsErrorDetail,
    ToolSettingsErrorEnvelope,
)
from opensprite_backend.tool_settings import ToolSettingsOperations


router = APIRouter()

TOOL_SETTINGS_ERROR_STATUS = {
    ToolSettingsErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    ToolSettingsErrorCode.TOOL_NOT_FOUND: status.HTTP_400_BAD_REQUEST,
    ToolSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ToolSettingsErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}
TOOL_SETTINGS_PUBLIC_ERRORS = {
    ToolSettingsErrorCode.INVALID_REQUEST: ("Request validation failed.", False),
    ToolSettingsErrorCode.TOOL_NOT_FOUND: ("The requested tool is unavailable.", False),
    ToolSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: ("Tool settings are unavailable.", True),
    ToolSettingsErrorCode.INTERNAL_ERROR: ("An internal error occurred.", False),
}
TOOL_CATALOG_ERROR_RESPONSES = {
    500: {"model": ToolSettingsErrorEnvelope},
    503: {"model": ToolSettingsErrorEnvelope},
}
TOOL_SETTINGS_PUT_ERROR_RESPONSES = {
    400: {"model": ToolSettingsErrorEnvelope},
    **TOOL_CATALOG_ERROR_RESPONSES,
}


def tool_settings_error_response(code: ToolSettingsErrorCode) -> JSONResponse:
    message, retryable = TOOL_SETTINGS_PUBLIC_ERRORS[code]
    envelope = ToolSettingsErrorEnvelope(
        error=ToolSettingsErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=TOOL_SETTINGS_ERROR_STATUS[code],
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _tool_settings(request: Request) -> ToolSettingsOperations:
    return cast(ToolSettingsOperations, request.app.state.tool_settings)


@router.get(
    "/api/tools",
    operation_id="listTools",
    response_model=ToolListResponse,
    responses=TOOL_CATALOG_ERROR_RESPONSES,
    tags=["tools"],
)
async def list_tools(
    settings: ToolSettingsOperations = Depends(_tool_settings),
) -> ToolListResponse:
    return await settings.list_tools()


@router.get(
    "/api/settings/tools",
    operation_id="getToolSettings",
    response_model=ToolSettings,
    responses=TOOL_CATALOG_ERROR_RESPONSES,
    tags=["tool-settings"],
)
async def get_tool_settings(
    settings: ToolSettingsOperations = Depends(_tool_settings),
) -> ToolSettings:
    return await settings.get()


@router.put(
    "/api/settings/tools",
    operation_id="putToolSettings",
    response_model=ToolSettings,
    responses=TOOL_SETTINGS_PUT_ERROR_RESPONSES,
    tags=["tool-settings"],
)
async def put_tool_settings(
    payload: PutToolSettingsRequest,
    settings: ToolSettingsOperations = Depends(_tool_settings),
) -> ToolSettings:
    return await settings.put(ToolSettings.model_validate(payload.model_dump()))
