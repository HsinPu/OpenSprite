"""User-initiated native local path picker route."""

from typing import cast

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from ..local_paths import LocalPathPickerOperations
from ..models import (
    LocalPathErrorDetail,
    LocalPathErrorCode,
    LocalPathErrorEnvelope,
    LocalPathPickRequest,
    LocalPathPickResponse,
)


router = APIRouter()

_ERRORS = {
    "invalid_request": (status.HTTP_400_BAD_REQUEST, "Request validation failed.", False),
    "invalid_selection": (status.HTTP_422_UNPROCESSABLE_ENTITY, "The selected path is not valid.", False),
    "picker_busy": (status.HTTP_409_CONFLICT, "Another path picker is already open.", True),
    "picker_unavailable": (status.HTTP_503_SERVICE_UNAVAILABLE, "The native path picker is unavailable.", True),
    "internal_error": (status.HTTP_500_INTERNAL_SERVER_ERROR, "An internal error occurred.", False),
}


def local_path_error_response(code: str) -> JSONResponse:
    status_code, message, retryable = _ERRORS.get(code, _ERRORS["internal_error"])
    envelope = LocalPathErrorEnvelope(
        error=LocalPathErrorDetail(
            code=cast(LocalPathErrorCode, code if code in _ERRORS else "internal_error"),
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _picker(request: Request) -> LocalPathPickerOperations:
    return cast(LocalPathPickerOperations, request.app.state.local_path_picker)


@router.post(
    "/api/local-paths/pick",
    operation_id="pickLocalPath",
    response_model=LocalPathPickResponse,
    responses={
        204: {"description": "Selection cancelled"},
        400: {"model": LocalPathErrorEnvelope},
        409: {"model": LocalPathErrorEnvelope},
        422: {"model": LocalPathErrorEnvelope},
        500: {"model": LocalPathErrorEnvelope},
        503: {"model": LocalPathErrorEnvelope},
    },
    tags=["local-paths"],
)
async def pick_local_path(
    payload: LocalPathPickRequest,
    picker: LocalPathPickerOperations = Depends(_picker),
) -> LocalPathPickResponse | Response:
    selected = await picker.pick(payload.kind)
    if selected is None:
        return Response(status_code=204)
    return LocalPathPickResponse(path=selected)
