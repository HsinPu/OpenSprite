"""Thin HTTP/SSE routes for the Agent chat application boundary."""

from __future__ import annotations

import re
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from opensprite_backend.conversations.models import RunStatus

from .chat_models import (
    CancelRunResponse,
    ChatErrorEnvelope,
    ConversationListResponse,
    MessageListResponse,
    RunResponse,
    StartRunRequest,
    StartRunResponse,
    conversation_list_response,
    message_list_response,
    run_response,
)
from .chat_service import AgentChatError, AgentChatOperations, ChatErrorCode
from .sse import run_event_frame


router = APIRouter(tags=["agent-chat"])
_EVENT_ID = re.compile(r"^(?:0|[1-9][0-9]{0,18})$")


def _errors(*codes: int) -> dict[int, dict[str, object]]:
    return {
        code: {
            "model": ChatErrorEnvelope,
            "description": "Fixed safe Agent chat error envelope.",
        }
        for code in codes
    }


def _agent_chat(request: Request) -> AgentChatOperations:
    return cast(AgentChatOperations, request.app.state.agent_chat)


@router.get(
    "/api/conversations",
    operation_id="listConversations",
    response_model=ConversationListResponse,
    responses=_errors(400, 500, 503),
)
async def list_conversations(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    chat: AgentChatOperations = Depends(_agent_chat),
) -> ConversationListResponse:
    page = await chat.list_conversations(limit=limit, before=before)
    return conversation_list_response(page)


@router.get(
    "/api/conversations/{conversation_id}/messages",
    operation_id="listConversationMessages",
    response_model=MessageListResponse,
    responses=_errors(400, 404, 500, 503),
)
async def list_conversation_messages(
    conversation_id: UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    before_sequence: Annotated[
        int | None,
        Query(alias="beforeSequence", ge=1),
    ] = None,
    chat: AgentChatOperations = Depends(_agent_chat),
) -> MessageListResponse:
    page = await chat.list_messages(
        str(conversation_id),
        limit=limit,
        before_sequence=before_sequence,
    )
    return message_list_response(page)


@router.post(
    "/api/runs",
    operation_id="startRun",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=StartRunResponse,
    responses=_errors(400, 409, 500, 503),
)
async def start_run(
    payload: StartRunRequest,
    chat: AgentChatOperations = Depends(_agent_chat),
) -> StartRunResponse:
    accepted = await chat.start_run(
        conversation_id=(
            None
            if payload.conversationId is None
            else str(payload.conversationId)
        ),
        client_request_id=str(payload.clientRequestId),
        message=payload.message,
    )
    return StartRunResponse(
        conversationId=accepted.conversation.id,
        runId=accepted.run.id,
    )


@router.get(
    "/api/runs/{run_id}",
    operation_id="getRun",
    response_model=RunResponse,
    responses=_errors(404, 500, 503),
)
async def get_run(
    run_id: UUID,
    chat: AgentChatOperations = Depends(_agent_chat),
) -> RunResponse:
    return run_response(await chat.get_run(str(run_id)))


@router.get(
    "/api/runs/{run_id}/events",
    operation_id="streamRunEvents",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Replayable semantic Run event stream.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        **_errors(400, 404, 500, 503),
    },
)
async def stream_run_events(
    run_id: UUID,
    last_event_id: Annotated[
        str | None,
        Header(alias="Last-Event-ID"),
    ] = None,
    chat: AgentChatOperations = Depends(_agent_chat),
) -> StreamingResponse:
    after_sequence = 0
    if last_event_id is not None:
        if _EVENT_ID.fullmatch(last_event_id) is None:
            raise AgentChatError(ChatErrorCode.INVALID_REQUEST)
        after_sequence = int(last_event_id)
    resolved_run_id = str(run_id)
    await chat.get_run(resolved_run_id)

    async def frames():
        async for event in chat.stream_events(
            resolved_run_id,
            after_sequence=after_sequence,
        ):
            yield run_event_frame(event)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/api/runs/{run_id}/cancel",
    operation_id="cancelRun",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CancelRunResponse,
    responses=_errors(400, 404, 409, 500, 503),
)
async def cancel_run(
    run_id: UUID,
    request: Request,
    chat: AgentChatOperations = Depends(_agent_chat),
) -> CancelRunResponse:
    if await request.body():
        raise AgentChatError(ChatErrorCode.INVALID_REQUEST)
    run = await chat.cancel_run(str(run_id))
    if run.status not in {RunStatus.CANCELLING, RunStatus.CANCELLED}:
        raise AgentChatError(ChatErrorCode.RUN_NOT_ACTIVE)
    return CancelRunResponse(runId=run.id, status=run.status.value)
