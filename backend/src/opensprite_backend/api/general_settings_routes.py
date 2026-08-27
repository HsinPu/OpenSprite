"""General-settings HTTP routes and public error serialization."""

from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from opensprite_backend.general_settings import GeneralSettingsOperations
from opensprite_backend.models import (
    GeneralSettings,
    GeneralSettingsErrorCode,
    GeneralSettingsErrorDetail,
    GeneralSettingsErrorEnvelope,
    PutGeneralSettingsRequest,
)

router = APIRouter()

GENERAL_SETTINGS_ERROR_STATUS = {
    GeneralSettingsErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    GeneralSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    GeneralSettingsErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}
GENERAL_SETTINGS_PUBLIC_ERRORS = {
    GeneralSettingsErrorCode.INVALID_REQUEST: ("Request validation failed.", False),
    GeneralSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: ("General settings are unavailable.", True),
    GeneralSettingsErrorCode.INTERNAL_ERROR: ("An internal error occurred.", False),
}
GENERAL_SETTINGS_GET_ERROR_RESPONSES = {
    500: {"model": GeneralSettingsErrorEnvelope},
    503: {"model": GeneralSettingsErrorEnvelope},
}
GENERAL_SETTINGS_PUT_ERROR_RESPONSES = {
    400: {"model": GeneralSettingsErrorEnvelope},
    500: {"model": GeneralSettingsErrorEnvelope},
    503: {"model": GeneralSettingsErrorEnvelope},
}


def general_settings_error_response(code: GeneralSettingsErrorCode) -> JSONResponse:
    message, retryable = GENERAL_SETTINGS_PUBLIC_ERRORS[code]
    envelope = GeneralSettingsErrorEnvelope(
        error=GeneralSettingsErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=GENERAL_SETTINGS_ERROR_STATUS[code],
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _general_settings(request: Request) -> GeneralSettingsOperations:
    return cast(GeneralSettingsOperations, request.app.state.general_settings)


@router.get(
    "/api/settings/general",
    operation_id="getGeneralSettings",
    response_model=GeneralSettings,
    responses=GENERAL_SETTINGS_GET_ERROR_RESPONSES,
    tags=["general-settings"],
)
async def get_general_settings(
    settings: GeneralSettingsOperations = Depends(_general_settings),
) -> GeneralSettings:
    return await settings.get()


@router.put(
    "/api/settings/general",
    operation_id="putGeneralSettings",
    response_model=GeneralSettings,
    responses=GENERAL_SETTINGS_PUT_ERROR_RESPONSES,
    tags=["general-settings"],
)
async def put_general_settings(
    payload: PutGeneralSettingsRequest,
    settings: GeneralSettingsOperations = Depends(_general_settings),
) -> GeneralSettings:
    return await settings.put(GeneralSettings.model_validate(payload.model_dump()))
