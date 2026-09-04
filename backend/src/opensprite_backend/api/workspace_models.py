"""Strict public models for Workspace management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from opensprite_backend.workspaces import WorkspaceCatalog, WorkspaceSummary


class WorkspaceContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateWorkspaceRequest(WorkspaceContractModel):
    name: str = Field(min_length=1, max_length=80)
    rootPath: str = Field(min_length=1, max_length=32768)
    expectedRevision: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank name")
        return value


class UpdateWorkspaceRequest(WorkspaceContractModel):
    name: str = Field(min_length=1, max_length=80)
    rootPath: str = Field(min_length=1, max_length=32768)
    expectedRevision: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank name")
        return value


class SetActiveWorkspaceRequest(WorkspaceContractModel):
    workspaceId: UUID
    expectedRevision: int = Field(ge=0)


class WorkspaceUsageResponse(WorkspaceContractModel):
    conversationCount: int = Field(ge=0)
    scheduleCount: int = Field(ge=0)
    activeRunCount: int = Field(ge=0)


class WorkspaceResponse(WorkspaceContractModel):
    id: UUID
    kind: Literal["unassigned", "directory"]
    name: str
    rootPath: str | None
    availability: Literal["available", "unavailable", "not_applicable"]
    unavailableReason: Literal[
        "missing", "not_directory", "access_denied", "unsafe"
    ] | None
    revision: int = Field(ge=1)
    createdAt: datetime
    updatedAt: datetime
    usage: WorkspaceUsageResponse


class WorkspaceCatalogResponse(WorkspaceContractModel):
    revision: int = Field(ge=0)
    activeWorkspaceId: UUID
    workspaces: list[WorkspaceResponse] = Field(max_length=101)


class WorkspaceErrorDetail(WorkspaceContractModel):
    code: Literal[
        "invalid_request",
        "unsafe_root",
        "duplicate_name",
        "duplicate_root",
        "revision_conflict",
        "not_found",
        "workspace_busy",
        "workspace_not_empty",
        "workspace_store_unavailable",
        "internal_error",
    ]
    message: str
    retryable: bool


class WorkspaceErrorEnvelope(WorkspaceContractModel):
    error: WorkspaceErrorDetail


def workspace_response(item: WorkspaceSummary) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=item.id,
        kind=item.kind.value,
        name=item.name,
        rootPath=item.root_path,
        availability=item.availability.value,
        unavailableReason=(
            None if item.unavailable_reason is None else item.unavailable_reason.value
        ),
        revision=item.revision,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
        usage=WorkspaceUsageResponse(
            conversationCount=item.usage.conversation_count,
            scheduleCount=item.usage.schedule_count,
            activeRunCount=item.usage.active_run_count,
        ),
    )


def workspace_catalog_response(item: WorkspaceCatalog) -> WorkspaceCatalogResponse:
    return WorkspaceCatalogResponse(
        revision=item.revision,
        activeWorkspaceId=item.active_workspace_id,
        workspaces=[workspace_response(workspace) for workspace in item.workspaces],
    )
