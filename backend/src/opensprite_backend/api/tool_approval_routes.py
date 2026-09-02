"""Short-lived Tool approval detail and decision routes."""

from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from opensprite_backend.models import (
    PutToolApprovalDecisionRequest,
    ToolApprovalDecisionResponse,
    ToolApprovalDetail,
    ToolApprovalErrorCode,
    ToolApprovalErrorDetail,
    ToolApprovalErrorEnvelope,
)
from opensprite_backend.tools.approval import ToolApprovalOperations


router = APIRouter()
APPROVAL_ERROR_STATUS = {
    ToolApprovalErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    ToolApprovalErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ToolApprovalErrorCode.APPROVAL_EXPIRED: status.HTTP_409_CONFLICT,
    ToolApprovalErrorCode.APPROVAL_ALREADY_DECIDED: status.HTTP_409_CONFLICT,
    ToolApprovalErrorCode.DATABASE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ToolApprovalErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}
APPROVAL_PUBLIC_ERRORS = {
    ToolApprovalErrorCode.INVALID_REQUEST: ("Request validation failed.", False),
    ToolApprovalErrorCode.NOT_FOUND: ("The Tool approval was not found.", False),
    ToolApprovalErrorCode.APPROVAL_EXPIRED: ("The Tool approval has expired.", False),
    ToolApprovalErrorCode.APPROVAL_ALREADY_DECIDED: ("The Tool approval was already decided.", False),
    ToolApprovalErrorCode.DATABASE_UNAVAILABLE: ("Conversation storage is unavailable.", True),
    ToolApprovalErrorCode.INTERNAL_ERROR: ("An internal error occurred.", False),
}
APPROVAL_ERROR_RESPONSES = {
    code: {"model": ToolApprovalErrorEnvelope}
    for code in (400, 404, 409, 500, 503)
}


def tool_approval_error_response(code: ToolApprovalErrorCode) -> JSONResponse:
    message, retryable = APPROVAL_PUBLIC_ERRORS[code]
    envelope = ToolApprovalErrorEnvelope(
        error=ToolApprovalErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=APPROVAL_ERROR_STATUS[code],
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _approvals(request: Request) -> ToolApprovalOperations:
    return cast(ToolApprovalOperations, request.app.state.tool_approvals)


@router.get("/api/tool-approvals/{approval_id}", operation_id="getToolApproval", response_model=ToolApprovalDetail, responses=APPROVAL_ERROR_RESPONSES, tags=["tool-approvals"])
async def get_tool_approval(approval_id: str, approvals: ToolApprovalOperations = Depends(_approvals)) -> ToolApprovalDetail:
    return await approvals.get(approval_id)


@router.put("/api/tool-approvals/{approval_id}", operation_id="putToolApprovalDecision", response_model=ToolApprovalDecisionResponse, responses=APPROVAL_ERROR_RESPONSES, tags=["tool-approvals"])
async def put_tool_approval_decision(approval_id: str, payload: PutToolApprovalDecisionRequest, approvals: ToolApprovalOperations = Depends(_approvals)) -> ToolApprovalDecisionResponse:
    return await approvals.decide(approval_id, payload.decision)
