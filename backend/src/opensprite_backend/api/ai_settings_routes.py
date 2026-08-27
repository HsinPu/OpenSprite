"""AI-settings HTTP routes and public error serialization."""

from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from opensprite_backend.ai_settings import AiSettingsOperations
from opensprite_backend.models import (
    AiSettings,
    AiSettingsErrorCode,
    AiSettingsErrorDetail,
    AiSettingsErrorEnvelope,
    PutAiSettingsRequest,
)


router = APIRouter()

AI_SETTINGS_ERROR_STATUS: dict[AiSettingsErrorCode, int] = {
    AiSettingsErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    AiSettingsErrorCode.NOT_CONNECTED: status.HTTP_409_CONFLICT,
    AiSettingsErrorCode.CREDENTIAL_STORE_UNAVAILABLE: (
        status.HTTP_503_SERVICE_UNAVAILABLE
    ),
    AiSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: (
        status.HTTP_503_SERVICE_UNAVAILABLE
    ),
    AiSettingsErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}

AI_SETTINGS_PUBLIC_ERRORS: dict[
    AiSettingsErrorCode, tuple[str, bool]
] = {
    AiSettingsErrorCode.INVALID_REQUEST: (
        "Request validation failed.",
        False,
    ),
    AiSettingsErrorCode.NOT_CONNECTED: (
        "The provider is not connected.",
        False,
    ),
    AiSettingsErrorCode.CREDENTIAL_STORE_UNAVAILABLE: (
        "Secure credential storage is unavailable.",
        True,
    ),
    AiSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: (
        "AI settings are unavailable.",
        True,
    ),
    AiSettingsErrorCode.INTERNAL_ERROR: (
        "An internal error occurred.",
        False,
    ),
}

AI_SETTINGS_GET_ERROR_RESPONSES = {
    500: {"model": AiSettingsErrorEnvelope},
    503: {"model": AiSettingsErrorEnvelope},
}
AI_SETTINGS_PUT_ERROR_RESPONSES = {
    400: {"model": AiSettingsErrorEnvelope},
    409: {"model": AiSettingsErrorEnvelope},
    500: {"model": AiSettingsErrorEnvelope},
    503: {"model": AiSettingsErrorEnvelope},
}


def ai_settings_error_response(code: AiSettingsErrorCode) -> JSONResponse:
    message, retryable = AI_SETTINGS_PUBLIC_ERRORS[code]
    envelope = AiSettingsErrorEnvelope(
        error=AiSettingsErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=AI_SETTINGS_ERROR_STATUS[code],
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _ai_settings(request: Request) -> AiSettingsOperations:
    return cast(AiSettingsOperations, request.app.state.ai_settings)


@router.get(
    "/api/settings/ai",
    operation_id="getAiSettings",
    response_model=AiSettings,
    responses=AI_SETTINGS_GET_ERROR_RESPONSES,
    tags=["ai-settings"],
)
async def get_ai_settings(
    settings: AiSettingsOperations = Depends(_ai_settings),
) -> AiSettings:
    return await settings.get()


@router.put(
    "/api/settings/ai",
    operation_id="putAiSettings",
    response_model=AiSettings,
    responses=AI_SETTINGS_PUT_ERROR_RESPONSES,
    tags=["ai-settings"],
)
async def put_ai_settings(
    payload: PutAiSettingsRequest,
    settings: AiSettingsOperations = Depends(_ai_settings),
) -> AiSettings:
    return await settings.put(AiSettings.model_validate(payload.model_dump()))
