"""Domain values for local OpenSprite workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


UNASSIGNED_WORKSPACE_ID = "00000000-0000-4000-8000-000000000000"
UNASSIGNED_WORKSPACE_NAME = "Unassigned workspace"


class WorkspaceKind(StrEnum):
    UNASSIGNED = "unassigned"
    DIRECTORY = "directory"


class WorkspaceAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class WorkspaceUnavailableReason(StrEnum):
    MISSING = "missing"
    NOT_DIRECTORY = "not_directory"
    ACCESS_DENIED = "access_denied"
    UNSAFE = "unsafe"


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: str
    name: str
    root_path: str
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceCatalogState:
    revision: int
    active_workspace_id: str
    workspaces: tuple[WorkspaceRecord, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceUsage:
    conversation_count: int = 0
    schedule_count: int = 0
    active_run_count: int = 0


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    id: str
    kind: WorkspaceKind
    name: str
    root_path: str | None
    availability: WorkspaceAvailability
    unavailable_reason: WorkspaceUnavailableReason | None
    revision: int
    created_at: datetime
    updated_at: datetime
    usage: WorkspaceUsage


@dataclass(frozen=True, slots=True)
class WorkspaceCatalog:
    revision: int
    active_workspace_id: str
    workspaces: tuple[WorkspaceSummary, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceExecutionContext:
    id: str
    kind: WorkspaceKind
    name: str
    root_path: str | None
    revision: int
    root_hash: str | None
    availability: WorkspaceAvailability
    unavailable_reason: WorkspaceUnavailableReason | None


def unassigned_workspace(usage: WorkspaceUsage | None = None) -> WorkspaceSummary:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return WorkspaceSummary(
        id=UNASSIGNED_WORKSPACE_ID,
        kind=WorkspaceKind.UNASSIGNED,
        name=UNASSIGNED_WORKSPACE_NAME,
        root_path=None,
        availability=WorkspaceAvailability.NOT_APPLICABLE,
        unavailable_reason=None,
        revision=1,
        created_at=epoch,
        updated_at=epoch,
        usage=usage or WorkspaceUsage(),
    )
