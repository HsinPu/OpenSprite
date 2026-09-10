"""Authenticated inspection routes for durable child-Agent executions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from opensprite_backend.application import AgentChatError, ChatErrorCode
from opensprite_backend.custom_agents.models import AgentError

from .custom_agent_routes import AgentErrorResponse


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


SubagentStatus = Literal[
    "queued",
    "running",
    "cancelling",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
    "timed_out",
]
from opensprite_backend.provider_identity import ProviderId


class SubagentSummary(StrictModel):
    id: str
    parentRunId: str
    agentId: str
    name: str = Field(min_length=1, max_length=80)
    revision: int = Field(ge=1)
    providerId: ProviderId
    modelId: str = Field(min_length=1, max_length=256)
    status: SubagentStatus
    errorCode: str | None = Field(
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]{0,79}$",
    )
    createdAt: str
    startedAt: str | None
    finishedAt: str | None


class SubagentList(StrictModel):
    items: list[SubagentSummary] = Field(max_length=6)


class SubagentResult(StrictModel):
    childId: str
    status: SubagentStatus
    error: str | None = Field(max_length=512)
    text: str = Field(max_length=4000)
    nextOffset: int | None = Field(ge=0)


router = APIRouter(tags=["subagents"])


def _identifier(value: str) -> str:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise AgentError("invalid_request") from None
    if str(parsed) != value:
        raise AgentError("invalid_request")
    return value


def _query(request: Request, allowed: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if key not in allowed or key in result:
            raise AgentError("invalid_request")
        result[key] = value
    return result


def _integer(value: str, *, maximum: int = 2**63 - 1) -> int:
    if not value or not value.isascii() or not value.isdigit() or len(value) > 19:
        raise AgentError("invalid_request")
    parsed = int(value)
    if parsed > maximum:
        raise AgentError("invalid_request")
    return parsed


def _timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AgentError("store_unavailable")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError):
        raise AgentError("store_unavailable") from None


def _store(request: Request):
    store = getattr(request.app.state, "child_executions", None)
    if store is None:
        raise AgentError("store_unavailable")
    return store


def _coordinator(request: Request):
    coordinator = getattr(request.app.state, "delegation", None)
    if coordinator is None:
        raise AgentError("store_unavailable")
    return coordinator


async def _parent_exists(request: Request, parent_id: str) -> None:
    chat = getattr(request.app.state, "agent_chat", None)
    if chat is None:
        raise AgentError("store_unavailable")
    try:
        await chat.get_run(parent_id)
    except AgentChatError as error:
        if error.code is ChatErrorCode.NOT_FOUND:
            raise AgentError("not_found") from None
        raise AgentError("store_unavailable") from None
    except AgentError:
        raise
    except Exception:
        # Do not expose provider, filesystem, database or traceback details.
        raise AgentError("store_unavailable") from None


async def _blocking(function, *args):
    """Run repository I/O without releasing the request's ownership context."""

    task = asyncio.create_task(asyncio.to_thread(function, *args))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        task.exception()
        raise asyncio.CancelledError
    try:
        return task.result()
    except AgentError:
        raise
    except Exception:
        raise AgentError("store_unavailable") from None


def _summary(child) -> SubagentSummary:
    try:
        identifier = _identifier(child.id)
        parent_identifier = _identifier(child.parent_run_id)
        agent_identifier = _identifier(child.agent_id)
        return SubagentSummary.model_validate(
            {
                "id": identifier,
                "parentRunId": parent_identifier,
                "agentId": agent_identifier,
                "name": child.agent_name,
                "revision": child.agent_revision,
                "providerId": child.provider_id,
                "modelId": child.model_id,
                "status": child.status,
                "errorCode": child.error_code,
                "createdAt": _timestamp(child.created_at),
                "startedAt": _timestamp(child.started_at),
                "finishedAt": _timestamp(child.finished_at),
            }
        )
    except (TypeError, ValueError, ValidationError):
        raise AgentError("store_unavailable") from None


def _result(child, offset: int) -> SubagentResult:
    text = child.result_text[offset : offset + 4000]
    next_offset = offset + len(text) if offset + len(text) < len(child.result_text) else None
    try:
        return SubagentResult.model_validate(
            {
                "childId": child.id,
                "status": child.status,
                "error": child.error_code,
                "text": text,
                "nextOffset": next_offset,
            }
        )
    except (TypeError, ValueError, ValidationError):
        raise AgentError("store_unavailable") from None


_ERROR_RESPONSES = {
    status: {"model": AgentErrorResponse, "description": description}
    for status, description in (
        (400, "Invalid child execution request"),
        (401, "Authentication required"),
        (404, "Parent run or child execution not found"),
        (409, "Child execution is not available for this operation"),
        (503, "Child execution store unavailable"),
    )
}


@router.get(
    "/api/runs/{parent_id}/agents",
    response_model=SubagentList,
    operation_id="listSubagents",
    responses=_ERROR_RESPONSES,
)
async def list_subagents(parent_id: str, request: Request) -> SubagentList:
    parent = _identifier(parent_id)
    _query(request, set())
    await _parent_exists(request, parent)
    children = await _blocking(_store(request).list, parent)
    if not isinstance(children, tuple) or len(children) > 6:
        raise AgentError("store_unavailable")
    return SubagentList(items=[_summary(child) for child in children])


@router.get(
    "/api/runs/{parent_id}/agents/{child_id}",
    response_model=SubagentResult,
    operation_id="getSubagentResult",
    responses=_ERROR_RESPONSES,
)
async def get_subagent_result(
    parent_id: str,
    child_id: str,
    request: Request,
) -> SubagentResult:
    parent = _identifier(parent_id)
    child_identifier = _identifier(child_id)
    params = _query(request, {"offset"})
    offset = _integer(params.get("offset", "0"))
    child = await _blocking(_store(request).get, parent, child_identifier)
    return _result(child, offset)


@router.post(
    "/api/runs/{parent_id}/agents/{child_id}/cancel",
    response_model=SubagentSummary,
    operation_id="cancelSubagent",
    responses=_ERROR_RESPONSES,
)
async def cancel_subagent(
    parent_id: str,
    child_id: str,
    request: Request,
) -> SubagentSummary:
    parent = _identifier(parent_id)
    child_identifier = _identifier(child_id)
    _query(request, set())
    if await request.body():
        raise AgentError("invalid_request")
    try:
        child = await _coordinator(request).cancel_child(parent, child_identifier)
    except AgentError:
        raise
    except Exception:
        raise AgentError("store_unavailable") from None
    return _summary(child)


__all__ = [
    "SubagentList",
    "SubagentResult",
    "SubagentSummary",
    "router",
]
