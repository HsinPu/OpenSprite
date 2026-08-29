"""Conversation-settings HTTP routes and public error serialization."""

from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from opensprite_backend.conversation_settings import ConversationSettingsOperations
from opensprite_backend.models import (
    ConversationSettings,
    ConversationSettingsErrorCode,
    ConversationSettingsErrorDetail,
    ConversationSettingsErrorEnvelope,
    PutConversationSettingsRequest,
)


router = APIRouter()

CONVERSATION_SETTINGS_ERROR_STATUS = {
    ConversationSettingsErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    ConversationSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ConversationSettingsErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}
CONVERSATION_SETTINGS_PUBLIC_ERRORS = {
    ConversationSettingsErrorCode.INVALID_REQUEST: ("Request validation failed.", False),
    ConversationSettingsErrorCode.SETTINGS_STORE_UNAVAILABLE: ("Conversation settings are unavailable.", True),
    ConversationSettingsErrorCode.INTERNAL_ERROR: ("An internal error occurred.", False),
}
CONVERSATION_SETTINGS_GET_ERROR_RESPONSES = {
    500: {"model": ConversationSettingsErrorEnvelope},
    503: {"model": ConversationSettingsErrorEnvelope},
}
CONVERSATION_SETTINGS_PUT_ERROR_RESPONSES = {
    400: {"model": ConversationSettingsErrorEnvelope},
    500: {"model": ConversationSettingsErrorEnvelope},
    503: {"model": ConversationSettingsErrorEnvelope},
}


def conversation_settings_error_response(
    code: ConversationSettingsErrorCode,
) -> JSONResponse:
    message, retryable = CONVERSATION_SETTINGS_PUBLIC_ERRORS[code]
    envelope = ConversationSettingsErrorEnvelope(
        error=ConversationSettingsErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=CONVERSATION_SETTINGS_ERROR_STATUS[code],
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _conversation_settings(request: Request) -> ConversationSettingsOperations:
    return cast(
        ConversationSettingsOperations,
        request.app.state.conversation_settings,
    )


@router.get(
    "/api/settings/conversation",
    operation_id="getConversationSettings",
    response_model=ConversationSettings,
    responses=CONVERSATION_SETTINGS_GET_ERROR_RESPONSES,
    tags=["conversation-settings"],
)
async def get_conversation_settings(
    settings: ConversationSettingsOperations = Depends(_conversation_settings),
) -> ConversationSettings:
    return await settings.get()


@router.put(
    "/api/settings/conversation",
    operation_id="putConversationSettings",
    response_model=ConversationSettings,
    responses=CONVERSATION_SETTINGS_PUT_ERROR_RESPONSES,
    tags=["conversation-settings"],
)
async def put_conversation_settings(
    payload: PutConversationSettingsRequest,
    settings: ConversationSettingsOperations = Depends(_conversation_settings),
) -> ConversationSettings:
    return await settings.put(
        ConversationSettings.model_validate(payload.model_dump())
    )
