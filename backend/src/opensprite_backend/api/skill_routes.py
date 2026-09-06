"""Authenticated, strict Skills management HTTP boundary."""
from __future__ import annotations

import asyncio
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from opensprite_backend.skills.models import StrictModel, SkillError, SkillRecord
from opensprite_backend.skills.service import unique

async def workspace_gate(request: Request):
    if request.method not in {"GET", "DELETE"} and request.query_params:
        raise SkillError("invalid_request")
    async with service(request).workspaces.mutation_gate.hold():
        yield


router = APIRouter(prefix="/api/skills", tags=["skills"], dependencies=[Depends(workspace_gate)])


class Revision(StrictModel):
    expectedRevision: int = Field(ge=0)


class Settings(Revision):
    enabled: bool


class Scope(StrictModel):
    scope: Literal["global", "workspace"]
    workspaceId: str | None = None


class Scan(Scope, Revision):
    pass


class Create(Scan):
    content: str = Field(max_length=65536)


class Update(Revision):
    content: str = Field(max_length=65536)


class Enabled(Settings):
    confirmedHash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Override(Revision):
    workspaceId: str
    disabled: bool


class SettingsResponse(StrictModel):
    enabled: bool
    revision: int = Field(ge=0)


class SkillView(SkillRecord):
    contentHash: str | None
    state: Literal["ready", "pending", "disabled", "missing", "invalid_format", "content_too_large", "unsafe_path", "workspace_unavailable"]
    effective: bool
    reason: str
    content: str | None = None


class SkillListResponse(SettingsResponse):
    skills: list[SkillView]


class SkillDetailResponse(StrictModel):
    revision: int = Field(ge=0)
    skill: SkillView


def request_schema(model):
    return {"requestBody": {"required": True, "content": {"application/json": {"schema": model.model_json_schema()}}}}


async def body(request: Request, model):
    raw = await request.body()
    if len(raw) > 400000:
        raise SkillError("invalid_request")
    try:
        return model.model_validate(json.loads(raw, object_pairs_hook=unique))
    except (ValueError, UnicodeError, ValidationError, SkillError):
        raise SkillError("invalid_request") from None


def identifier(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError:
        raise SkillError("invalid_request") from None


def query(request: Request, allowed: set[str]):
    result = {}
    for key, value in request.query_params.multi_items():
        if key not in allowed or key in result:
            raise SkillError("invalid_request")
        result[key] = value
    return result


def service(request: Request):
    result = getattr(request.app.state, "skills", None)
    if result is None:
        raise SkillError("store_unavailable")
    return result


async def skill_error_handler(request: Request, error: SkillError):
    code = error.code
    status = 503 if code == "store_unavailable" else 404 if code == "not_found" else 409 if code in {
        "revision_conflict", "content_changed", "duplicate_name", "skill_limit_reached", "workspace_unavailable"
    } else 400
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": "Skill operation could not be completed.",
        "retryable": status in (409, 503),
    }})


@router.get("/settings", operation_id="getSkillsSettings", response_model=SettingsResponse)
async def get_settings(request: Request):
    query(request, set())
    return await asyncio.to_thread(service(request).settings)


@router.put("/settings", operation_id="putSkillsSettings", response_model=SettingsResponse, openapi_extra=request_schema(Settings))
async def put_settings(request: Request):
    value = await body(request, Settings)
    return await asyncio.to_thread(service(request).configure, expected=value.expectedRevision, enabled=value.enabled)


@router.get("", operation_id="listSkills", response_model=SkillListResponse, response_model_exclude_unset=True, openapi_extra={"parameters": [
    {"name": "scope", "in": "query", "required": True, "schema": {"type": "string", "enum": ["global", "workspace"]}},
    {"name": "workspaceId", "in": "query", "required": False, "description": "Required for workspace scope; global scope uses this to calculate workspace overrides.", "schema": {"type": "string", "format": "uuid"}},
]})
async def list_skills(request: Request):
    params = query(request, {"scope", "workspaceId"})
    try:
        value = Scope.model_validate(params)
    except ValidationError:
        raise SkillError("invalid_request") from None
    if value.workspaceId is not None:
        value.workspaceId = identifier(value.workspaceId)
    if value.scope == "workspace" and value.workspaceId is None:
        raise SkillError("invalid_request")
    return await asyncio.to_thread(service(request).list, value.scope, value.workspaceId)


@router.post("", operation_id="createSkill", response_model=SkillDetailResponse, openapi_extra=request_schema(Create))
async def create_skill(request: Request):
    value = await body(request, Create)
    if value.workspaceId is not None:
        value.workspaceId = identifier(value.workspaceId)
    return await asyncio.to_thread(service(request).save, scope=value.scope, workspace_id=value.workspaceId,
                                   content=value.content, expected=value.expectedRevision)


@router.post("/scan", operation_id="scanSkills", response_model=SkillListResponse, response_model_exclude_unset=True, openapi_extra=request_schema(Scan))
async def scan_skills(request: Request):
    value = await body(request, Scan)
    if value.workspaceId is not None:
        value.workspaceId = identifier(value.workspaceId)
    return await asyncio.to_thread(service(request).scan, value.scope, value.workspaceId, value.expectedRevision)


@router.get("/{skill_id}", operation_id="getSkill", response_model=SkillDetailResponse)
async def get_skill(skill_id: str, request: Request):
    query(request, set())
    return await asyncio.to_thread(service(request).get, identifier(skill_id))


@router.put("/{skill_id}", operation_id="updateSkill", response_model=SkillDetailResponse, openapi_extra=request_schema(Update))
async def update_skill(skill_id: str, request: Request):
    value = await body(request, Update)
    manager = service(request)
    item = await asyncio.to_thread(manager.get, identifier(skill_id))
    item = item["skill"]
    return await asyncio.to_thread(manager.save, scope=item["scope"], workspace_id=item["workspaceId"], content=value.content,
                                   expected=value.expectedRevision, identifier=identifier(skill_id))


@router.delete("/{skill_id}", operation_id="deleteSkill", response_model=None, openapi_extra={"parameters": [
    {"name": "expectedRevision", "in": "query", "required": True, "schema": {"type": "integer", "minimum": 0}},
], "responses": {"200": {"description": "Archived or already missing directory; registration removed.", "content": {"application/json": {"schema": {"type": "null"}}}}}})
async def delete_skill(skill_id: str, request: Request):
    params = query(request, {"expectedRevision"})
    raw = params.get("expectedRevision", "")
    if not raw.isascii() or not raw.isdigit():
        raise SkillError("invalid_request")
    return await asyncio.to_thread(service(request).delete, identifier(skill_id), int(raw))


@router.put("/{skill_id}/enabled", operation_id="setSkillEnabled", response_model=SettingsResponse, openapi_extra=request_schema(Enabled))
async def enable_skill(skill_id: str, request: Request):
    value = await body(request, Enabled)
    return await asyncio.to_thread(service(request).configure, expected=value.expectedRevision,
                                   identifier=identifier(skill_id), enabled=value.enabled,
                                   confirmed_hash=value.confirmedHash)


@router.put("/{skill_id}/workspace-override", operation_id="setSkillWorkspaceOverride", response_model=SettingsResponse, openapi_extra=request_schema(Override))
async def override_skill(skill_id: str, request: Request):
    value = await body(request, Override)
    return await asyncio.to_thread(service(request).configure, expected=value.expectedRevision,
                                   identifier=identifier(skill_id), workspace_id=identifier(value.workspaceId),
                                   disabled=value.disabled)
