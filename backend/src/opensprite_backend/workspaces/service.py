"""Application boundary for Workspace catalog mutations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import asyncio
import unicodedata
from typing import AsyncIterator, Callable, Protocol
from uuid import uuid4

from .models import (
    UNASSIGNED_WORKSPACE_ID,
    WorkspaceAvailability,
    WorkspaceCatalog,
    WorkspaceCatalogState,
    WorkspaceExecutionContext,
    WorkspaceKind,
    WorkspaceRecord,
    WorkspaceSummary,
    WorkspaceUsage,
    unassigned_workspace,
)
from .policy import InvalidWorkspaceRoot, UnsafeWorkspaceRoot, WorkspaceRootPolicy
from .store import WorkspaceStore, WorkspaceStoreError


class WorkspaceFailure(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNSAFE_ROOT = "unsafe_root"
    DUPLICATE_NAME = "duplicate_name"
    DUPLICATE_ROOT = "duplicate_root"
    REVISION_CONFLICT = "revision_conflict"
    NOT_FOUND = "not_found"
    WORKSPACE_BUSY = "workspace_busy"
    WORKSPACE_NOT_EMPTY = "workspace_not_empty"
    WORKSPACE_STORE_UNAVAILABLE = "workspace_store_unavailable"
    INTERNAL_ERROR = "internal_error"


class WorkspaceError(Exception):
    def __init__(self, failure: WorkspaceFailure) -> None:
        self.failure = failure
        super().__init__(failure.value)


class WorkspaceUsageReader(Protocol):
    def workspace_usage(self, workspace_id: str) -> WorkspaceUsage: ...


class EmptyWorkspaceUsageReader:
    def workspace_usage(self, workspace_id: str) -> WorkspaceUsage:
        del workspace_id
        return WorkspaceUsage()


class WorkspaceOperations(Protocol):
    async def list(self) -> WorkspaceCatalog: ...
    async def get(self, workspace_id: str) -> WorkspaceSummary: ...
    async def create(self, *, name: str, root_path: str, expected_revision: int) -> WorkspaceCatalog: ...
    async def update(self, workspace_id: str, *, name: str, root_path: str, expected_revision: int) -> WorkspaceSummary: ...
    async def delete(self, workspace_id: str, *, expected_revision: int) -> None: ...
    async def set_active(self, workspace_id: str, *, expected_revision: int) -> WorkspaceCatalog: ...


class WorkspaceResolver(Protocol):
    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext: ...


class UnassignedWorkspaceResolver:
    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext:
        if workspace_id != UNASSIGNED_WORKSPACE_ID:
            raise WorkspaceError(WorkspaceFailure.NOT_FOUND)
        return WorkspaceExecutionContext(
            id=UNASSIGNED_WORKSPACE_ID,
            kind=WorkspaceKind.UNASSIGNED,
            name=unassigned_workspace().name,
            root_path=None,
            revision=1,
            root_hash=None,
            availability=WorkspaceAvailability.NOT_APPLICABLE,
            unavailable_reason=None,
        )


class WorkspaceMutationGate:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def hold(self) -> AsyncIterator[None]:
        async with self._lock:
            yield


class UnavailableWorkspaces:
    async def _raise(self):
        raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)

    async def list(self): return await self._raise()
    async def get(self, workspace_id: str): del workspace_id; return await self._raise()
    async def create(self, **kwargs): del kwargs; return await self._raise()
    async def update(self, workspace_id: str, **kwargs): del workspace_id, kwargs; return await self._raise()
    async def delete(self, workspace_id: str, **kwargs): del workspace_id, kwargs; await self._raise()
    async def set_active(self, workspace_id: str, **kwargs): del workspace_id, kwargs; return await self._raise()

    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext:
        del workspace_id
        raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)


class WorkspaceCatalogService:
    def __init__(
        self,
        store: WorkspaceStore,
        root_policy: WorkspaceRootPolicy,
        *,
        usage_reader: WorkspaceUsageReader | None = None,
        mutation_gate: WorkspaceMutationGate | None = None,
        clock: Callable[[], datetime] | None = None,
        identifier_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._root_policy = root_policy
        self._usage = usage_reader or EmptyWorkspaceUsageReader()
        self.mutation_gate = mutation_gate or WorkspaceMutationGate()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier_factory = identifier_factory or (lambda: str(uuid4()))

    async def list(self) -> WorkspaceCatalog:
        state = self._state()
        return self._catalog(state)

    async def get(self, workspace_id: str) -> WorkspaceSummary:
        state = self._state()
        if workspace_id == UNASSIGNED_WORKSPACE_ID:
            return unassigned_workspace(self._usage_for(workspace_id))
        record = self._find(state, workspace_id)
        return self._summary(record)

    async def create(
        self, *, name: str, root_path: str, expected_revision: int
    ) -> WorkspaceCatalog:
        async with self.mutation_gate.hold():
            state = self._state()
            if expected_revision != state.revision:
                raise WorkspaceError(WorkspaceFailure.REVISION_CONFLICT)
            if len(state.workspaces) >= 100:
                raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
            normalized_name = self._name(name)
            canonical_root = self._root(root_path)
            self._require_unique(state, normalized_name, canonical_root)
            now = self._now()
            identifier = self._identifier_factory()
            if not self._valid_identifier(identifier) or identifier == UNASSIGNED_WORKSPACE_ID:
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)
            record = WorkspaceRecord(
                identifier, normalized_name, canonical_root, 1, now, now
            )
            next_state = WorkspaceCatalogState(
                state.revision + 1,
                identifier,
                (*state.workspaces, record),
            )
            self._write(next_state)
            return self._catalog(next_state)

    async def update(
        self,
        workspace_id: str,
        *,
        name: str,
        root_path: str,
        expected_revision: int,
    ) -> WorkspaceSummary:
        if workspace_id == UNASSIGNED_WORKSPACE_ID:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        async with self.mutation_gate.hold():
            state = self._state()
            current = self._find(state, workspace_id)
            if current.revision != expected_revision:
                raise WorkspaceError(WorkspaceFailure.REVISION_CONFLICT)
            normalized_name = self._name(name)
            canonical_root = self._root(root_path)
            root_changed = (
                self._root_policy.comparison_key(current.root_path)
                != self._root_policy.comparison_key(canonical_root)
            )
            if root_changed and self._usage_for(workspace_id).active_run_count:
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_BUSY)
            self._require_unique(
                state, normalized_name, canonical_root, excluding=workspace_id
            )
            updated = replace(
                current,
                name=normalized_name,
                root_path=canonical_root,
                revision=current.revision + 1,
                updated_at=self._now(),
            )
            next_state = replace(
                state,
                revision=state.revision + 1,
                workspaces=tuple(
                    updated if item.id == workspace_id else item
                    for item in state.workspaces
                ),
            )
            self._write(next_state)
            return self._summary(updated)

    async def delete(self, workspace_id: str, *, expected_revision: int) -> None:
        if workspace_id == UNASSIGNED_WORKSPACE_ID:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        async with self.mutation_gate.hold():
            state = self._state()
            current = self._find(state, workspace_id)
            if current.revision != expected_revision:
                raise WorkspaceError(WorkspaceFailure.REVISION_CONFLICT)
            usage = self._usage_for(workspace_id)
            if usage.active_run_count:
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_BUSY)
            if usage.conversation_count or usage.schedule_count:
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_NOT_EMPTY)
            next_state = WorkspaceCatalogState(
                state.revision + 1,
                (
                    UNASSIGNED_WORKSPACE_ID
                    if state.active_workspace_id == workspace_id
                    else state.active_workspace_id
                ),
                tuple(item for item in state.workspaces if item.id != workspace_id),
            )
            self._write(next_state)

    async def set_active(
        self, workspace_id: str, *, expected_revision: int
    ) -> WorkspaceCatalog:
        async with self.mutation_gate.hold():
            state = self._state()
            if state.revision != expected_revision:
                raise WorkspaceError(WorkspaceFailure.REVISION_CONFLICT)
            if workspace_id != UNASSIGNED_WORKSPACE_ID:
                self._find(state, workspace_id)
            if state.active_workspace_id == workspace_id:
                return self._catalog(state)
            next_state = replace(
                state,
                revision=state.revision + 1,
                active_workspace_id=workspace_id,
            )
            self._write(next_state)
            return self._catalog(next_state)

    def snapshot_record(self, workspace_id: str) -> WorkspaceRecord | None:
        state = self._state()
        if workspace_id == UNASSIGNED_WORKSPACE_ID:
            return None
        return self._find(state, workspace_id)

    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext:
        if workspace_id == UNASSIGNED_WORKSPACE_ID:
            return UnassignedWorkspaceResolver().execution_context(workspace_id)
        record = self._find(self._state(), workspace_id)
        status = self._root_policy.inspect_saved_root(record.root_path)
        return WorkspaceExecutionContext(
            id=record.id,
            kind=WorkspaceKind.DIRECTORY,
            name=record.name,
            root_path=record.root_path,
            revision=record.revision,
            root_hash=hashlib.sha256(record.root_path.encode("utf-8")).hexdigest(),
            availability=status.availability,
            unavailable_reason=status.unavailable_reason,
        )

    def _catalog(self, state: WorkspaceCatalogState) -> WorkspaceCatalog:
        summaries = [
            unassigned_workspace(
                self._usage_for(UNASSIGNED_WORKSPACE_ID)
            )
        ]
        summaries.extend(self._summary(item) for item in state.workspaces)
        return WorkspaceCatalog(state.revision, state.active_workspace_id, tuple(summaries))

    def _summary(self, item: WorkspaceRecord) -> WorkspaceSummary:
        status = self._root_policy.inspect_saved_root(item.root_path)
        return WorkspaceSummary(
            item.id,
            WorkspaceKind.DIRECTORY,
            item.name,
            item.root_path,
            status.availability,
            status.unavailable_reason,
            item.revision,
            item.created_at,
            item.updated_at,
            self._usage_for(item.id),
        )

    def _usage_for(self, workspace_id: str) -> WorkspaceUsage:
        try:
            return self._usage.workspace_usage(workspace_id)
        except WorkspaceError:
            raise
        except Exception:
            raise WorkspaceError(
                WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE
            ) from None

    def _state(self) -> WorkspaceCatalogState:
        try:
            return self._store.get()
        except WorkspaceStoreError:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE) from None

    def _write(self, state: WorkspaceCatalogState) -> None:
        try:
            self._store.set(state)
        except WorkspaceStoreError:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE) from None

    @staticmethod
    def _find(state: WorkspaceCatalogState, workspace_id: str) -> WorkspaceRecord:
        item = next((item for item in state.workspaces if item.id == workspace_id), None)
        if item is None:
            raise WorkspaceError(WorkspaceFailure.NOT_FOUND)
        return item

    @staticmethod
    def _name(value: str) -> str:
        if type(value) is not str:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        normalized = unicodedata.normalize("NFC", value).strip()
        if (
            not normalized
            or len(normalized) > 80
            or any(ord(character) < 32 for character in normalized)
        ):
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        return normalized

    def _root(self, value: str) -> str:
        try:
            return self._root_policy.validate_new_root(value)
        except UnsafeWorkspaceRoot:
            raise WorkspaceError(WorkspaceFailure.UNSAFE_ROOT) from None
        except InvalidWorkspaceRoot:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST) from None

    def _require_unique(
        self,
        state: WorkspaceCatalogState,
        name: str,
        root: str,
        *,
        excluding: str | None = None,
    ) -> None:
        root_key = self._root_policy.comparison_key(root)
        for item in state.workspaces:
            if item.id == excluding:
                continue
            if item.name.casefold() == name.casefold():
                raise WorkspaceError(WorkspaceFailure.DUPLICATE_NAME)
            if self._root_policy.comparison_key(item.root_path) == root_key:
                raise WorkspaceError(WorkspaceFailure.DUPLICATE_ROOT)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _valid_identifier(value: str) -> bool:
        from uuid import UUID

        try:
            parsed = UUID(value)
        except (TypeError, ValueError, AttributeError):
            return False
        return str(parsed) == value and parsed.version == 4
