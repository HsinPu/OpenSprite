"""Authenticated custom-agent management with strict JSON/query contracts."""

from __future__ import annotations

import asyncio
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from opensprite_backend.custom_agents.models import AgentError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Revision(StrictModel):
    expectedRevision: int = Field(ge=0)


class Settings(Revision):
    enabled: bool


class Scope(StrictModel):
    scope: Literal["global", "workspace"]
    workspaceId: str | None = None

    @model_validator(mode="after")
    def check_scope(self):
        if (self.scope == "workspace") != (self.workspaceId is not None):
            raise ValueError("invalid_scope")
        if self.workspaceId is not None:
            self.workspaceId = identifier(self.workspaceId)
        return self


class Scan(Scope, Revision):
    pass


class Create(Scan):
    content: str = Field(max_length=65536)


class Update(Revision):
    content: str = Field(max_length=65536)


class Batch(Scan):
    ids: list[str] = Field(min_length=1)
    action: Literal["enable", "disable", "remove"]

    @model_validator(mode="after")
    def check_ids(self):
        self.ids = [identifier(value) for value in self.ids]
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("duplicate_id")
        return self


class SettingsView(StrictModel):
    enabled: bool
    revision: int = Field(ge=0)


class AgentView(StrictModel):
    id: str
    scope: Literal["global", "workspace"]
    workspaceId: str | None
    fileName: str
    name: str
    description: str
    revision: int = Field(ge=1)
    enabled: bool
    reason: Literal["effective", "disabled", "master_disabled", "shadowed_by_workspace", "duplicate_name", "missing", "invalid_format", "content_too_large", "unsafe_path", "workspace_unavailable"]
    shadowedByAgentId: str | None
    providerId: str | None
    model: str | None
    contentHash: str | None


class AgentDetail(AgentView):
    content: str | None
    developerInstructions: str | None


class AgentList(StrictModel):
    revision: int = Field(ge=0)
    items: list[AgentView]
    nextCursor: str | None


class ScanView(StrictModel):
    revision: int = Field(ge=0)
    added: int = Field(ge=0)


class BatchView(StrictModel):
    revision: int = Field(ge=0)
    affected: int = Field(ge=0)


class AgentErrorDetail(StrictModel):
    code: str
    message: str
    retryable: bool


class AgentErrorResponse(StrictModel):
    error: AgentErrorDetail


def service(request: Request):
    value = getattr(request.app.state, "custom_agents", None)
    if value is None:
        raise AgentError("store_unavailable")
    return value


async def gate(request: Request):
    if request.method not in {"GET", "DELETE"} and request.query_params:
        raise AgentError("invalid_request")
    async with service(request).workspaces.mutation_gate.hold():
        yield


router = APIRouter(prefix="/api/agents", tags=["agents"], dependencies=[Depends(gate)], responses={
    status: {"model": AgentErrorResponse, "description": description}
    for status, description in [(400, "Invalid request or definition"), (401, "Authentication required"),
                                (404, "Agent not found"), (409, "Revision or workspace conflict"),
                                (503, "Agent catalog unavailable")]
})


def identifier(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise AgentError("invalid_request") from None


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_field")
        result[key] = value
    return result


async def body(request: Request, model):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise AgentError("invalid_request")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 512 * 1024:
            raise AgentError("invalid_request")
    try:
        return model.model_validate(json.loads(raw, object_pairs_hook=unique))
    except (ValueError, UnicodeError, ValidationError, RecursionError):
        raise AgentError("invalid_request") from None


def query(request: Request, allowed: set[str]):
    result = {}
    for key, value in request.query_params.multi_items():
        if key not in allowed or key in result:
            raise AgentError("invalid_request")
        result[key] = value
    return result


def integer(value: str, minimum=0, maximum=2**63 - 1) -> int:
    if not value.isascii() or not value.isdigit() or len(value) > 19:
        raise AgentError("invalid_request")
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise AgentError("invalid_request")
    return parsed


async def execute(function, *args):
    # A cancelled HTTP request must not release the Workspace gate while its
    # filesystem transaction is still running in the worker thread.
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        # Retrieve a failure so no detached exception remains unobserved.
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


def schema(model):
    return {"requestBody": {"required": True, "content": {"application/json": {"schema": model.model_json_schema()}}}}


async def agent_error_handler(request: Request, error: AgentError):
    status = 503 if error.code == "store_unavailable" else 404 if error.code == "not_found" else 409 if error.code in {"revision_conflict", "duplicate_name", "workspace_unavailable", "file_exists"} else 400
    return JSONResponse(status_code=status, content={"error": {"code": error.code, "message": "Agent operation could not be completed.", "retryable": status in {409, 503}}})


@router.get("/settings", response_model=SettingsView, operation_id="getAgentsSettings")
async def settings(request: Request):
    query(request, set())
    return await execute(service(request).settings)


@router.put("/settings", response_model=SettingsView, operation_id="setAgentsSettings", openapi_extra=schema(Settings))
async def set_settings(request: Request):
    value = await body(request, Settings)
    return await execute(service(request).set_settings, value.enabled, value.expectedRevision)


@router.get("", response_model=AgentList, operation_id="listAgents", openapi_extra={"parameters": [
    {"name": "scope", "in": "query", "required": True, "schema": {"type": "string", "enum": ["global", "workspace"]}},
    {"name": "workspaceId", "in": "query", "required": False, "description": "Required only for workspace scope.", "schema": {"type": "string", "format": "uuid"}},
    {"name": "cursor", "in": "query", "required": False, "schema": {"type": "string", "maxLength": 1024}},
    {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}},
]})
async def list_agents(request: Request):
    params = query(request, {"scope", "workspaceId", "cursor", "limit"})
    limit = integer(params.pop("limit", "50"), 1, 100)
    cursor = params.pop("cursor", None)
    if cursor is not None and (not cursor or len(cursor) > 1024):
        raise AgentError("invalid_request")
    try:
        value = Scope.model_validate(params)
    except ValidationError:
        raise AgentError("invalid_request") from None
    return await execute(service(request).list_agents, value.scope, value.workspaceId, cursor, limit)


@router.post("", response_model=AgentView, operation_id="createAgent", status_code=201, openapi_extra=schema(Create))
async def create(request: Request):
    value = await body(request, Create)
    return await execute(service(request).create, value.scope, value.workspaceId, value.content, value.expectedRevision)


@router.post("/scan", response_model=ScanView, operation_id="scanAgents", openapi_extra=schema(Scan))
async def scan(request: Request):
    value = await body(request, Scan)
    return await execute(service(request).scan, value.scope, value.workspaceId, value.expectedRevision)


@router.post("/batch", response_model=BatchView, operation_id="batchAgents", openapi_extra=schema(Batch))
async def batch(request: Request):
    value = await body(request, Batch)
    return await execute(service(request).batch, value.scope, value.workspaceId, value.ids, value.action, value.expectedRevision)


@router.get("/{agent_id}", response_model=AgentDetail, operation_id="getAgent")
async def get(agent_id: str, request: Request):
    query(request, set())
    return await execute(service(request).get, identifier(agent_id))


@router.put("/{agent_id}", response_model=AgentView, operation_id="updateAgent", openapi_extra=schema(Update))
async def update(agent_id: str, request: Request):
    value = await body(request, Update)
    return await execute(service(request).update, identifier(agent_id), value.content, value.expectedRevision)


@router.put("/{agent_id}/enabled", response_model=AgentView, operation_id="setAgentEnabled", openapi_extra=schema(Settings))
async def set_enabled(agent_id: str, request: Request):
    value = await body(request, Settings)
    return await execute(service(request).set_enabled, identifier(agent_id), value.enabled, value.expectedRevision)


@router.delete("/{agent_id}", status_code=204, operation_id="deleteAgent", openapi_extra={"parameters": [
    {"name": "expectedRevision", "in": "query", "required": True, "schema": {"type": "integer", "minimum": 0}},
]})
async def remove(agent_id: str, request: Request):
    params = query(request, {"expectedRevision"})
    expected = integer(params.get("expectedRevision", ""))
    await execute(service(request).remove, identifier(agent_id), expected)
    return Response(status_code=204)
