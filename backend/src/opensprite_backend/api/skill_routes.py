"""Authenticated, strict Skills management HTTP boundary."""
from __future__ import annotations

import asyncio
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from opensprite_backend.skills.models import StrictModel, SkillError
from opensprite_backend.skills.service import unique

router = APIRouter(prefix="/api/skills", tags=["skills"])


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


@router.get("/settings")
async def get_settings(request: Request):
    query(request, set())
    return await asyncio.to_thread(service(request).settings)


@router.put("/settings")
async def put_settings(request: Request):
    value = await body(request, Settings)
    return await asyncio.to_thread(service(request).configure, expected=value.expectedRevision, enabled=value.enabled)


@router.get("")
async def list_skills(request: Request):
    params = query(request, {"scope", "workspaceId"})
    try:
        value = Scope.model_validate(params)
    except ValidationError:
        raise SkillError("invalid_request") from None
    if value.workspaceId is not None:
        identifier(value.workspaceId)
    if value.scope == "workspace" and value.workspaceId is None:
        raise SkillError("invalid_request")
    return await asyncio.to_thread(service(request).list, value.scope, value.workspaceId)


@router.post("")
async def create_skill(request: Request):
    value = await body(request, Create)
    if value.workspaceId is not None:
        identifier(value.workspaceId)
    return await asyncio.to_thread(service(request).save, scope=value.scope, workspace_id=value.workspaceId,
                                   content=value.content, expected=value.expectedRevision)


@router.post("/scan")
async def scan_skills(request: Request):
    value = await body(request, Scan)
    if value.workspaceId is not None:
        identifier(value.workspaceId)
    return await asyncio.to_thread(service(request).scan, value.scope, value.workspaceId, value.expectedRevision)


@router.get("/{skill_id}")
async def get_skill(skill_id: str, request: Request):
    query(request, set())
    return await asyncio.to_thread(service(request).get, identifier(skill_id))


@router.put("/{skill_id}")
async def update_skill(skill_id: str, request: Request):
    value = await body(request, Update)
    manager = service(request)
    item = await asyncio.to_thread(manager.get, identifier(skill_id))
    item = item["skill"]
    return await asyncio.to_thread(manager.save, scope=item["scope"], workspace_id=item["workspaceId"], content=value.content,
                                   expected=value.expectedRevision, identifier=skill_id)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, request: Request):
    params = query(request, {"expectedRevision"})
    raw = params.get("expectedRevision", "")
    if not raw.isascii() or not raw.isdigit():
        raise SkillError("invalid_request")
    return await asyncio.to_thread(service(request).delete, identifier(skill_id), int(raw))


@router.put("/{skill_id}/enabled")
async def enable_skill(skill_id: str, request: Request):
    value = await body(request, Enabled)
    return await asyncio.to_thread(service(request).configure, expected=value.expectedRevision,
                                   identifier=identifier(skill_id), enabled=value.enabled,
                                   confirmed_hash=value.confirmedHash)


@router.put("/{skill_id}/workspace-override")
async def override_skill(skill_id: str, request: Request):
    value = await body(request, Override)
    return await asyncio.to_thread(service(request).configure, expected=value.expectedRevision,
                                   identifier=identifier(skill_id), workspace_id=identifier(value.workspaceId),
                                   disabled=value.disabled)
