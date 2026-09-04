"""Domain values for managed OpenSprite workspaces and directory mounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


DEFAULT_WORKSPACE_ID = "00000000-0000-4000-8000-000000000000"
DEFAULT_WORKSPACE_NAME = "Default workspace"
DEFAULT_WORKSPACE_DIRECTORY = "default"
EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"


class WorkspaceKind(StrEnum):
    DEFAULT = "default"
    MANAGED = "managed"


class WorkspaceAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class WorkspaceUnavailableReason(StrEnum):
    MISSING = "missing"
    NOT_DIRECTORY = "not_directory"
    ACCESS_DENIED = "access_denied"
    UNSAFE = "unsafe"
    OVERLAP = "overlap"


class WorkspaceMountAccess(StrEnum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


@dataclass(frozen=True, slots=True)
class WorkspaceMountRecord:
    id: str
    alias: str
    root_path: str
    access_mode: WorkspaceMountAccess
    enabled: bool
    disabled_reason: WorkspaceUnavailableReason | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: str
    name: str
    directory_name: str
    mounts: tuple[WorkspaceMountRecord, ...]
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceCatalogState:
    revision: int
    active_workspace_id: str
    workspaces: tuple[WorkspaceRecord, ...]
    default_revision: int = 1
    default_mounts: tuple[WorkspaceMountRecord, ...] = ()
    default_updated_at: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    source_version: int = 2


@dataclass(frozen=True, slots=True)
class WorkspaceUsage:
    conversation_count: int = 0
    schedule_count: int = 0
    active_run_count: int = 0


@dataclass(frozen=True, slots=True)
class WorkspaceMountSummary:
    id: str
    alias: str
    root_path: str
    root_hash: str
    access_mode: WorkspaceMountAccess
    enabled: bool
    availability: WorkspaceAvailability
    unavailable_reason: WorkspaceUnavailableReason | None


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    id: str
    kind: WorkspaceKind
    name: str
    directory_name: str
    root_path: str
    availability: WorkspaceAvailability
    unavailable_reason: WorkspaceUnavailableReason | None
    mounts: tuple[WorkspaceMountSummary, ...]
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
class WorkspaceMountExecutionContext:
    id: str
    alias: str
    root_path: str
    root_hash: str
    access_mode: WorkspaceMountAccess
    enabled: bool
    availability: WorkspaceAvailability
    unavailable_reason: WorkspaceUnavailableReason | None


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
    directory_name: str = ""
    mounts: tuple[WorkspaceMountExecutionContext, ...] = ()
    mount_manifest_hash: str = EMPTY_WORKSPACE_MOUNT_MANIFEST_HASH


@dataclass(frozen=True, slots=True)
class WorkspaceImportCandidate:
    directory_name: str
    root_path: str


@dataclass(frozen=True, slots=True)
class WorkspaceImportCandidatePage:
    candidates: tuple[WorkspaceImportCandidate, ...]
    next_cursor: str | None
