"""Strict consumer-visible models for Conversation and Run HTTP routes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from opensprite_backend.conversations.models import (
    ConversationPage,
    ConversationSummary,
    Message,
    MessagePage,
    RunSnapshot,
)

from opensprite_backend.application import ChatErrorCode


class ChatContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
        alias_generator=lambda value: value.split("_")[0]
        + "".join(part.capitalize() for part in value.split("_")[1:]),
    )


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversationId: UUID | None
    clientRequestId: UUID
    message: str = Field(min_length=1, max_length=32768)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class StartRunResponse(ChatContractModel):
    conversation_id: UUID
    run_id: UUID
    status: Literal["queued"] = "queued"


class ConversationResponse(ChatContractModel):
    id: UUID
    title: str
    latest_message_preview: str | None
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(ChatContractModel):
    conversations: list[ConversationResponse] = Field(max_length=100)
    next_cursor: str | None


class MessageResponse(ChatContractModel):
    id: UUID
    conversation_id: UUID
    run_id: UUID
    role: Literal["user", "assistant"]
    content: str
    sequence: int = Field(ge=1)
    created_at: datetime


class MessageListResponse(ChatContractModel):
    messages: list[MessageResponse] = Field(max_length=200)
    next_before_sequence: int | None


class RunErrorResponse(ChatContractModel):
    code: ChatErrorCode
    message: str
    retryable: bool


class RunResponse(ChatContractModel):
    id: UUID
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID | None
    provider_id: Literal["openai", "anthropic", "openrouter"]
    model_id: str
    response_mode: Literal["default", "fast", "balanced", "deep"]
    status: Literal[
        "queued",
        "running",
        "cancelling",
        "completed",
        "failed",
        "cancelled",
        "interrupted",
    ]
    completion_reason: Literal["stop", "output_limit", "context_limit"] | None
    error: RunErrorResponse | None
    partial_text: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CancelRunResponse(ChatContractModel):
    run_id: UUID
    status: Literal["cancelling", "cancelled"]


class ChatErrorDetail(ChatContractModel):
    code: ChatErrorCode
    message: str
    retryable: bool


class ChatErrorEnvelope(ChatContractModel):
    error: ChatErrorDetail


_ERRORS: dict[ChatErrorCode, tuple[int, str, bool]] = {
    ChatErrorCode.INVALID_REQUEST: (400, "送出的對話資料無效。", False),
    ChatErrorCode.NOT_FOUND: (404, "找不到指定的對話或執行。", False),
    ChatErrorCode.RUN_BUSY: (409, "這個對話目前已有執行中的回覆。", True),
    ChatErrorCode.RUN_NOT_ACTIVE: (409, "這次執行目前無法取消。", False),
    ChatErrorCode.MODEL_NOT_SELECTED: (409, "尚未選擇可使用的 AI 模型。", False),
    ChatErrorCode.PROVIDER_NOT_CONNECTED: (409, "選擇的模型廠家尚未連線。", False),
    ChatErrorCode.INVALID_CREDENTIALS: (422, "模型廠家的 API 金鑰無效或已失效。", False),
    ChatErrorCode.PROVIDER_RATE_LIMITED: (429, "模型廠家目前限制請求。", True),
    ChatErrorCode.PROVIDER_TIMEOUT: (504, "模型廠家回應逾時。", True),
    ChatErrorCode.PROVIDER_UNREACHABLE: (502, "暫時無法連線到模型廠家。", True),
    ChatErrorCode.CREDENTIAL_STORE_UNAVAILABLE: (503, "安全憑證儲存暫時無法使用。", True),
    ChatErrorCode.SETTINGS_STORE_UNAVAILABLE: (503, "AI 設定暫時無法讀取。", True),
    ChatErrorCode.DATABASE_UNAVAILABLE: (503, "本機對話資料暫時無法使用。", True),
    ChatErrorCode.AGENT_LIMIT_REACHED: (409, "本次執行已達安全步驟上限。", False),
    ChatErrorCode.CONTEXT_LIMIT_EXCEEDED: (409, "必要的近期對話超過目前選擇的內容上限。", False),
    ChatErrorCode.CONTEXT_PREPARATION_FAILED: (502, "暫時無法準備這次對話的模型內容。", True),
    ChatErrorCode.TOOL_FAILURE: (502, "工具執行失敗。", False),
    ChatErrorCode.SCHEDULED_TOOL_APPROVAL_REQUIRED: (409, "排程無法執行需要人工核准的工具。", False),
    ChatErrorCode.INVALID_PROVIDER_RESPONSE: (502, "模型廠家的回應無法安全使用。", False),
    ChatErrorCode.INTERNAL_ERROR: (500, "本機服務暫時無法完成操作。", True),
}


def chat_error_response(code: ChatErrorCode) -> JSONResponse:
    status, message, retryable = _ERRORS[code]
    body = ChatErrorEnvelope(
        error=ChatErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def conversation_response(item: ConversationSummary) -> ConversationResponse:
    return ConversationResponse(
        id=item.id,
        title=item.title,
        latestMessagePreview=item.latest_message_preview,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


def conversation_list_response(page: ConversationPage) -> ConversationListResponse:
    return ConversationListResponse(
        conversations=[conversation_response(item) for item in page.items],
        nextCursor=page.next_cursor,
    )


def message_response(item: Message) -> MessageResponse:
    return MessageResponse(
        id=item.id,
        conversationId=item.conversation_id,
        runId=item.run_id,
        role=item.role,
        content=item.content,
        sequence=item.sequence,
        createdAt=item.created_at,
    )


def message_list_response(page: MessagePage) -> MessageListResponse:
    return MessageListResponse(
        messages=[message_response(item) for item in page.items],
        nextBeforeSequence=page.next_before_sequence,
    )


def run_response(item: RunSnapshot) -> RunResponse:
    error = (
        None
        if item.error is None
        else RunErrorResponse(
            code=ChatErrorCode(item.error.code),
            message=item.error.message,
            retryable=item.error.retryable,
        )
    )
    return RunResponse(
        id=item.id,
        conversationId=item.conversation_id,
        userMessageId=item.user_message_id,
        assistantMessageId=item.assistant_message_id,
        providerId=item.provider_id,
        modelId=item.model_id,
        responseMode=item.response_mode,
        status=item.status.value,
        completionReason=(
            None
            if item.completion_reason is None
            else item.completion_reason.value
        ),
        error=error,
        partialText=item.partial_text,
        createdAt=item.created_at,
        startedAt=item.started_at,
        finishedAt=item.finished_at,
    )
