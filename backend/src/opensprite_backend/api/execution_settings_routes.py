"""Execution plugin selection routes and sanitized public failures."""

from typing import cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from opensprite_backend.execution_settings import (
    ExecutionSettings, ExecutionSettingsErrorCode, ExecutionSettingsErrorDetail,
    ExecutionSettingsErrorEnvelope, ExecutionSettingsOperations, PutExecutionSettingsRequest,
)

router = APIRouter()

_ERRORS = {
    ExecutionSettingsErrorCode.INVALID_REQUEST: (400, "Request validation failed.", False),
    ExecutionSettingsErrorCode.PLUGIN_UNAVAILABLE: (503, "Execution plugins are unavailable.", True),
    ExecutionSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: (503, "Execution settings are unavailable.", True),
    ExecutionSettingsErrorCode.REVISION_CONFLICT: (409, "Execution settings changed. Reload before applying.", False),
    ExecutionSettingsErrorCode.MIGRATION_REQUIRED: (409, "Choose an API v3 Agent Loop in execution settings.", False),
    ExecutionSettingsErrorCode.INTERNAL_ERROR: (500, "An internal error occurred.", False),
}
GET_ERROR_RESPONSES = {500: {"model": ExecutionSettingsErrorEnvelope}, 503: {"model": ExecutionSettingsErrorEnvelope}}
PUT_ERROR_RESPONSES = {400: {"model": ExecutionSettingsErrorEnvelope}, 409: {"model": ExecutionSettingsErrorEnvelope}, **GET_ERROR_RESPONSES}


def execution_settings_error_response(code: ExecutionSettingsErrorCode) -> JSONResponse:
    status_code, message, retryable = _ERRORS[code]
    body = ExecutionSettingsErrorEnvelope(error=ExecutionSettingsErrorDetail(code=code, message=message, retryable=retryable))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json", by_alias=True))


def _execution_settings(request: Request) -> ExecutionSettingsOperations:
    return cast(ExecutionSettingsOperations, request.app.state.execution_settings)


@router.get("/api/settings/execution", operation_id="getExecutionSettings", response_model=ExecutionSettings, responses=GET_ERROR_RESPONSES, tags=["execution-settings"])
async def get_execution_settings(settings: ExecutionSettingsOperations = Depends(_execution_settings)) -> ExecutionSettings:
    return await settings.get()


@router.put("/api/settings/execution", operation_id="putExecutionSettings", response_model=ExecutionSettings, responses=PUT_ERROR_RESPONSES, tags=["execution-settings"])
async def put_execution_settings(payload: PutExecutionSettingsRequest, settings: ExecutionSettingsOperations = Depends(_execution_settings)) -> ExecutionSettings:
    return await settings.update(payload.pluginId, payload.expectedRevision)
