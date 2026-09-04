"""Strict public models for managed Workspace and mount APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from opensprite_backend.workspaces import (
    WorkspaceCatalog,
    WorkspaceImportCandidatePage,
    WorkspaceSummary,
)


class WorkspaceContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateWorkspaceRequest(WorkspaceContractModel):
    name: str = Field(min_length=1, max_length=80)
    expectedRevision: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank name")
        return value


class ImportWorkspaceRequest(WorkspaceContractModel):
    directoryName: str = Field(min_length=1, max_length=80)
    expectedRevision: int = Field(ge=0)


class UpdateWorkspaceRequest(WorkspaceContractModel):
    name: str = Field(min_length=1, max_length=80)
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


class MountWorkspaceRequest(WorkspaceContractModel):
    alias: str = Field(min_length=1, max_length=40)
    rootPath: str = Field(min_length=1, max_length=32768)
    accessMode: Literal["read_only", "read_write"] = "read_only"
    enabled: bool = True
    expectedRevision: int = Field(ge=1)

    @field_validator("alias")
    @classmethod
    def reject_blank_alias(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank alias")
        return value


class WorkspaceUsageResponse(WorkspaceContractModel):
    conversationCount: int = Field(ge=0)
    scheduleCount: int = Field(ge=0)
    activeRunCount: int = Field(ge=0)


class WorkspaceMountResponse(WorkspaceContractModel):
    id: UUID
    alias: str
    rootPath: str
    rootHash: str = Field(pattern=r"^[0-9a-f]{64}$")
    accessMode: Literal["read_only", "read_write"]
    enabled: bool
    availability: Literal["available", "unavailable", "not_applicable"]
    unavailableReason: Literal[
        "missing", "not_directory", "access_denied", "unsafe", "overlap"
    ] | None


class WorkspaceResponse(WorkspaceContractModel):
    id: UUID
    kind: Literal["default", "managed"]
    name: str
    directoryName: str
    rootPath: str
    availability: Literal["available", "unavailable"]
    unavailableReason: Literal[
        "missing", "not_directory", "access_denied", "unsafe", "overlap"
    ] | None
    mounts: list[WorkspaceMountResponse] = Field(max_length=20)
    revision: int = Field(ge=1)
    createdAt: datetime
    updatedAt: datetime
    usage: WorkspaceUsageResponse


class WorkspaceCatalogResponse(WorkspaceContractModel):
    revision: int = Field(ge=0)
    activeWorkspaceId: UUID
    workspaces: list[WorkspaceResponse] = Field(min_length=1, max_length=101)


class WorkspaceImportCandidateResponse(WorkspaceContractModel):
    directoryName: str
    rootPath: str


class WorkspaceImportCandidatePageResponse(WorkspaceContractModel):
    candidates: list[WorkspaceImportCandidateResponse] = Field(max_length=100)
    nextCursor: str | None


class WorkspaceErrorDetail(WorkspaceContractModel):
    code: Literal[
        "invalid_request",
        "invalid_directory_name",
        "unsafe_root",
        "duplicate_name",
        "duplicate_root",
        "managed_root_exists",
        "mount_limit_reached",
        "duplicate_mount_alias",
        "overlapping_root",
        "revision_conflict",
        "not_found",
        "mount_not_found",
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
        directoryName=item.directory_name,
        rootPath=item.root_path,
        availability=item.availability.value,
        unavailableReason=(
            None if item.unavailable_reason is None else item.unavailable_reason.value
        ),
        mounts=[
            WorkspaceMountResponse(
                id=mount.id,
                alias=mount.alias,
                rootPath=mount.root_path,
                rootHash=mount.root_hash,
                accessMode=mount.access_mode.value,
                enabled=mount.enabled,
                availability=mount.availability.value,
                unavailableReason=(
                    None
                    if mount.unavailable_reason is None
                    else mount.unavailable_reason.value
                ),
            )
            for mount in item.mounts
        ],
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


def import_candidate_page_response(
    item: WorkspaceImportCandidatePage,
) -> WorkspaceImportCandidatePageResponse:
    return WorkspaceImportCandidatePageResponse(
        candidates=[
            WorkspaceImportCandidateResponse(
                directoryName=candidate.directory_name,
                rootPath=candidate.root_path,
            )
            for candidate in item.candidates
        ],
        nextCursor=item.next_cursor,
    )
