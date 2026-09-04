"""Authenticated Workspace management routes."""

from __future__ import annotations

import json
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse

from opensprite_backend.workspaces import (
    WorkspaceError,
    WorkspaceFailure,
    WorkspaceOperations,
)

from .workspace_models import (
    CreateWorkspaceRequest,
    SetActiveWorkspaceRequest,
    UpdateWorkspaceRequest,
    WorkspaceCatalogResponse,
    WorkspaceErrorDetail,
    WorkspaceErrorEnvelope,
    WorkspaceResponse,
    workspace_catalog_response,
    workspace_response,
)


router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _workspaces(request: Request) -> WorkspaceOperations:
    return cast(WorkspaceOperations, request.app.state.workspaces)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


async def strict_json(request: Request) -> None:
    body = await request.body()
    try:
        json.loads(body.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST) from None


def workspace_error_response(failure: WorkspaceFailure) -> JSONResponse:
    http_status, message, retryable = {
        WorkspaceFailure.INVALID_REQUEST: (400, "Workspace request is invalid.", False),
        WorkspaceFailure.UNSAFE_ROOT: (400, "Workspace root is not allowed.", False),
        WorkspaceFailure.DUPLICATE_NAME: (409, "Workspace name is already in use.", False),
        WorkspaceFailure.DUPLICATE_ROOT: (409, "Workspace root is already in use.", False),
        WorkspaceFailure.REVISION_CONFLICT: (409, "Workspace was updated elsewhere.", True),
        WorkspaceFailure.NOT_FOUND: (404, "Workspace was not found.", False),
        WorkspaceFailure.WORKSPACE_BUSY: (409, "Workspace has an active run.", True),
        WorkspaceFailure.WORKSPACE_NOT_EMPTY: (409, "Workspace is not empty.", False),
        WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE: (503, "Workspace settings are unavailable.", True),
        WorkspaceFailure.INTERNAL_ERROR: (500, "An internal error occurred.", False),
    }[failure]
    envelope = WorkspaceErrorEnvelope(
        error=WorkspaceErrorDetail(
            code=failure.value,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=http_status,
        content=envelope.model_dump(mode="json"),
    )


def _expected_revision(request: Request) -> int:
    items = request.query_params.multi_items()
    if len(items) != 1 or items[0][0] != "expectedRevision":
        raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
    try:
        value = int(items[0][1])
    except (TypeError, ValueError):
        raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST) from None
    if value < 1:
        raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
    return value


@router.get("", operation_id="listWorkspaces", response_model=WorkspaceCatalogResponse)
async def list_workspaces(
    workspaces: WorkspaceOperations = Depends(_workspaces),
) -> WorkspaceCatalogResponse:
    return workspace_catalog_response(await workspaces.list())


@router.post(
    "",
    operation_id="createWorkspace",
    status_code=status.HTTP_201_CREATED,
    response_model=WorkspaceCatalogResponse,
    dependencies=[Depends(strict_json)],
)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    workspaces: WorkspaceOperations = Depends(_workspaces),
) -> WorkspaceCatalogResponse:
    return workspace_catalog_response(
        await workspaces.create(
            name=payload.name,
            root_path=payload.rootPath,
            expected_revision=payload.expectedRevision,
        )
    )


@router.put(
    "/active",
    operation_id="setActiveWorkspace",
    response_model=WorkspaceCatalogResponse,
    dependencies=[Depends(strict_json)],
)
async def set_active_workspace(
    payload: SetActiveWorkspaceRequest,
    workspaces: WorkspaceOperations = Depends(_workspaces),
) -> WorkspaceCatalogResponse:
    return workspace_catalog_response(
        await workspaces.set_active(
            str(payload.workspaceId),
            expected_revision=payload.expectedRevision,
        )
    )


@router.get(
    "/{workspace_id}",
    operation_id="getWorkspace",
    response_model=WorkspaceResponse,
)
async def get_workspace(
    workspace_id: UUID,
    workspaces: WorkspaceOperations = Depends(_workspaces),
) -> WorkspaceResponse:
    return workspace_response(await workspaces.get(str(workspace_id)))


@router.put(
    "/{workspace_id}",
    operation_id="updateWorkspace",
    response_model=WorkspaceResponse,
    dependencies=[Depends(strict_json)],
)
async def update_workspace(
    workspace_id: UUID,
    payload: UpdateWorkspaceRequest,
    workspaces: WorkspaceOperations = Depends(_workspaces),
) -> WorkspaceResponse:
    return workspace_response(
        await workspaces.update(
            str(workspace_id),
            name=payload.name,
            root_path=payload.rootPath,
            expected_revision=payload.expectedRevision,
        )
    )


@router.delete(
    "/{workspace_id}",
    operation_id="deleteWorkspace",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workspace(
    workspace_id: UUID,
    request: Request,
    expectedRevision: Annotated[int, Query(ge=1)],
    workspaces: WorkspaceOperations = Depends(_workspaces),
) -> Response:
    if await request.body():
        raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
    strict_revision = _expected_revision(request)
    if strict_revision != expectedRevision:
        raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
    await workspaces.delete(
        str(workspace_id),
        expected_revision=strict_revision,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
