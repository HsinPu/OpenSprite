"""Application boundary for managed Workspace and mount mutations."""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import logging
from pathlib import Path
from typing import AsyncIterator, Callable, Protocol
import unicodedata
from uuid import uuid4

from .models import (
    DEFAULT_WORKSPACE_DIRECTORY,
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
    WorkspaceAvailability,
    WorkspaceCatalog,
    WorkspaceCatalogState,
    WorkspaceExecutionContext,
    WorkspaceImportCandidate,
    WorkspaceImportCandidatePage,
    WorkspaceKind,
    WorkspaceMountAccess,
    WorkspaceMountExecutionContext,
    WorkspaceMountRecord,
    WorkspaceMountSummary,
    WorkspaceRecord,
    WorkspaceSummary,
    WorkspaceUnavailableReason,
    WorkspaceUsage,
)
from .policy import (
    InvalidWorkspaceDirectoryName,
    InvalidWorkspaceRoot,
    UnsafeWorkspaceRoot,
    WorkspaceRootPolicy,
)
from .store import WorkspaceStore, WorkspaceStoreError


_LOGGER = logging.getLogger("opensprite.workspaces")


class WorkspaceFailure(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_DIRECTORY_NAME = "invalid_directory_name"
    UNSAFE_ROOT = "unsafe_root"
    DUPLICATE_NAME = "duplicate_name"
    DUPLICATE_ROOT = "duplicate_root"
    MANAGED_ROOT_EXISTS = "managed_root_exists"
    MOUNT_LIMIT_REACHED = "mount_limit_reached"
    DUPLICATE_MOUNT_ALIAS = "duplicate_mount_alias"
    OVERLAPPING_ROOT = "overlapping_root"
    REVISION_CONFLICT = "revision_conflict"
    NOT_FOUND = "not_found"
    MOUNT_NOT_FOUND = "mount_not_found"
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
    async def startup(self) -> None: ...
    async def list(self) -> WorkspaceCatalog: ...
    async def get(self, workspace_id: str) -> WorkspaceSummary: ...
    async def create(self, *, name: str, expected_revision: int) -> WorkspaceCatalog: ...
    async def import_existing(self, *, directory_name: str, expected_revision: int) -> WorkspaceCatalog: ...
    async def import_candidates(self, *, limit: int, before: str | None) -> WorkspaceImportCandidatePage: ...
    async def update(self, workspace_id: str, *, name: str, expected_revision: int) -> WorkspaceSummary: ...
    async def delete(self, workspace_id: str, *, expected_revision: int) -> None: ...
    async def set_active(self, workspace_id: str, *, expected_revision: int) -> WorkspaceCatalog: ...
    async def add_mount(self, workspace_id: str, *, alias: str, root_path: str, access_mode: WorkspaceMountAccess, enabled: bool, expected_revision: int) -> WorkspaceSummary: ...
    async def update_mount(self, workspace_id: str, mount_id: str, *, alias: str, root_path: str, access_mode: WorkspaceMountAccess, enabled: bool, expected_revision: int) -> WorkspaceSummary: ...
    async def delete_mount(self, workspace_id: str, mount_id: str, *, expected_revision: int) -> WorkspaceSummary: ...


class WorkspaceResolver(Protocol):
    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext: ...


class DefaultWorkspaceResolver:
    def __init__(self, root_path: Path | None = None) -> None:
        self._root = None if root_path is None else root_path.resolve(strict=False)

    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext:
        if workspace_id != DEFAULT_WORKSPACE_ID:
            raise WorkspaceError(WorkspaceFailure.NOT_FOUND)
        root = None if self._root is None else str(self._root)
        availability = WorkspaceAvailability.NOT_APPLICABLE
        reason = None
        if self._root is not None:
            availability = (
                WorkspaceAvailability.AVAILABLE
                if self._root.is_dir()
                else WorkspaceAvailability.UNAVAILABLE
            )
            reason = None if availability is WorkspaceAvailability.AVAILABLE else WorkspaceUnavailableReason.MISSING
        return WorkspaceExecutionContext(
            id=DEFAULT_WORKSPACE_ID,
            kind=WorkspaceKind.DEFAULT,
            name=DEFAULT_WORKSPACE_NAME,
            root_path=root,
            revision=1,
            root_hash=None if root is None else _root_hash(root),
            availability=availability,
            unavailable_reason=reason,
            directory_name=DEFAULT_WORKSPACE_DIRECTORY,
            mounts=(),
            mount_manifest_hash=_mount_manifest_hash(()),
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

    async def startup(self): return await self._raise()
    async def list(self): return await self._raise()
    async def get(self, workspace_id: str): del workspace_id; return await self._raise()
    async def create(self, **kwargs): del kwargs; return await self._raise()
    async def import_existing(self, **kwargs): del kwargs; return await self._raise()
    async def import_candidates(self, **kwargs): del kwargs; return await self._raise()
    async def update(self, workspace_id: str, **kwargs): del workspace_id, kwargs; return await self._raise()
    async def delete(self, workspace_id: str, **kwargs): del workspace_id, kwargs; await self._raise()
    async def set_active(self, workspace_id: str, **kwargs): del workspace_id, kwargs; return await self._raise()
    async def add_mount(self, workspace_id: str, **kwargs): del workspace_id, kwargs; return await self._raise()
    async def update_mount(self, workspace_id: str, mount_id: str, **kwargs): del workspace_id, mount_id, kwargs; return await self._raise()
    async def delete_mount(self, workspace_id: str, mount_id: str, **kwargs): del workspace_id, mount_id, kwargs; return await self._raise()

    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext:
        del workspace_id
        raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)


class WorkspaceCatalogService:
    def __init__(
        self,
        store: WorkspaceStore,
        root_policy: WorkspaceRootPolicy,
        managed_root: Path | None = None,
        *,
        usage_reader: WorkspaceUsageReader | None = None,
        mutation_gate: WorkspaceMutationGate | None = None,
        clock: Callable[[], datetime] | None = None,
        identifier_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._root_policy = root_policy
        self._managed_root = (
            managed_root
            if managed_root is not None
            else root_policy.user_home / "OpenSprite" / "workspace"
        ).resolve(strict=False)
        self._usage = usage_reader or EmptyWorkspaceUsageReader()
        self.mutation_gate = mutation_gate or WorkspaceMutationGate()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier_factory = identifier_factory or (lambda: str(uuid4()))

    async def startup(self) -> None:
        async with self.mutation_gate.hold():
            state = self._state()
            try:
                self._ensure_directory(self._managed_root)
                self._ensure_directory(self._managed_path(DEFAULT_WORKSPACE_DIRECTORY))
            except WorkspaceError:
                _LOGGER.warning("managed Workspace root is unavailable")
                return
            if state.source_version == 1:
                state = self._disable_legacy_managed_overlaps(state)
                created: list[Path] = []
                try:
                    for item in state.workspaces:
                        path = self._managed_path(item.directory_name)
                        if not path.exists():
                            self._ensure_directory(path)
                            created.append(path)
                    self._write(replace(state, source_version=2))
                except WorkspaceError:
                    for path in reversed(created):
                        try:
                            path.rmdir()
                        except OSError:
                            pass
                    _LOGGER.warning("Workspace catalog v1 migration was deferred")

    async def list(self) -> WorkspaceCatalog:
        return self._catalog(self._state())

    async def get(self, workspace_id: str) -> WorkspaceSummary:
        state = self._state()
        if workspace_id == DEFAULT_WORKSPACE_ID:
            return self._default_summary(state)
        return self._summary(self._find(state, workspace_id))

    async def create(self, *, name: str, expected_revision: int) -> WorkspaceCatalog:
        async with self.mutation_gate.hold():
            state = self._state()
            self._require_catalog_revision(state, expected_revision)
            if len(state.workspaces) >= 100:
                raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
            directory_name = self._directory_name(name)
            normalized_name = self._name(name)
            self._require_unique_name_and_directory(state, normalized_name, directory_name)
            path = self._managed_path(directory_name)
            if path.exists():
                raise WorkspaceError(WorkspaceFailure.MANAGED_ROOT_EXISTS)
            now = self._now()
            identifier = self._new_identifier()
            self._ensure_directory(path)
            try:
                record = WorkspaceRecord(identifier, normalized_name, directory_name, (), 1, now, now)
                next_state = replace(
                    state,
                    revision=state.revision + 1,
                    active_workspace_id=identifier,
                    workspaces=(*state.workspaces, record),
                    source_version=2,
                )
                self._write(next_state)
            except WorkspaceError:
                try:
                    path.rmdir()
                except OSError:
                    pass
                raise
            return self._catalog(next_state)

    async def import_existing(
        self, *, directory_name: str, expected_revision: int
    ) -> WorkspaceCatalog:
        async with self.mutation_gate.hold():
            state = self._state()
            self._require_catalog_revision(state, expected_revision)
            if len(state.workspaces) >= 100:
                raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
            normalized_directory = self._directory_name(directory_name)
            self._require_unique_name_and_directory(state, normalized_directory, normalized_directory)
            path = self._managed_path(normalized_directory)
            if not path.exists() or not path.is_dir() or path.is_symlink():
                raise WorkspaceError(WorkspaceFailure.NOT_FOUND)
            status = self._root_policy.inspect_saved_root(str(path))
            if status.availability is not WorkspaceAvailability.AVAILABLE:
                raise WorkspaceError(WorkspaceFailure.UNSAFE_ROOT)
            now = self._now()
            identifier = self._new_identifier()
            record = WorkspaceRecord(identifier, normalized_directory, normalized_directory, (), 1, now, now)
            next_state = replace(
                state,
                revision=state.revision + 1,
                active_workspace_id=identifier,
                workspaces=(*state.workspaces, record),
                source_version=2,
            )
            self._write(next_state)
            return self._catalog(next_state)

    async def import_candidates(
        self, *, limit: int, before: str | None
    ) -> WorkspaceImportCandidatePage:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        cursor = self._decode_cursor(before) if before is not None else None
        state = self._state()
        registered = {item.directory_name.casefold() for item in state.workspaces}
        registered.add(DEFAULT_WORKSPACE_DIRECTORY.casefold())
        try:
            paths = sorted(
                (
                    path for path in self._managed_root.iterdir()
                    if path.is_dir()
                    and not path.is_symlink()
                    and path.name.casefold() not in registered
                    and self._safe_directory(path.name)
                ),
                key=lambda item: (item.name.casefold(), item.name),
            )
        except OSError:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE) from None
        if cursor is not None:
            paths = [path for path in paths if (path.name.casefold(), path.name) > cursor]
        selected = paths[: limit + 1]
        page = selected[:limit]
        next_cursor = self._encode_cursor(page[-1].name) if len(selected) > limit and page else None
        return WorkspaceImportCandidatePage(
            tuple(WorkspaceImportCandidate(path.name, str(path.resolve(strict=False))) for path in page),
            next_cursor,
        )

    async def update(
        self, workspace_id: str, *, name: str, expected_revision: int
    ) -> WorkspaceSummary:
        if workspace_id == DEFAULT_WORKSPACE_ID:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        async with self.mutation_gate.hold():
            state = self._state()
            current = self._find(state, workspace_id)
            self._require_item_revision(current.revision, expected_revision)
            normalized_name = self._name(name)
            self._require_unique_name_and_directory(
                state, normalized_name, current.directory_name, excluding=workspace_id
            )
            updated = replace(
                current,
                name=normalized_name,
                revision=current.revision + 1,
                updated_at=self._now(),
            )
            next_state = self._replace_record(state, updated)
            self._write(next_state)
            return self._summary(updated)

    async def delete(self, workspace_id: str, *, expected_revision: int) -> None:
        if workspace_id == DEFAULT_WORKSPACE_ID:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        async with self.mutation_gate.hold():
            state = self._state()
            current = self._find(state, workspace_id)
            self._require_item_revision(current.revision, expected_revision)
            usage = self._usage_for(workspace_id)
            if usage.active_run_count:
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_BUSY)
            if usage.conversation_count or usage.schedule_count:
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_NOT_EMPTY)
            next_state = replace(
                state,
                revision=state.revision + 1,
                active_workspace_id=(
                    DEFAULT_WORKSPACE_ID
                    if state.active_workspace_id == workspace_id
                    else state.active_workspace_id
                ),
                workspaces=tuple(item for item in state.workspaces if item.id != workspace_id),
                source_version=2,
            )
            self._write(next_state)

    async def set_active(
        self, workspace_id: str, *, expected_revision: int
    ) -> WorkspaceCatalog:
        async with self.mutation_gate.hold():
            state = self._state()
            self._require_catalog_revision(state, expected_revision)
            if workspace_id != DEFAULT_WORKSPACE_ID:
                self._find(state, workspace_id)
            if state.active_workspace_id == workspace_id:
                return self._catalog(state)
            next_state = replace(
                state,
                revision=state.revision + 1,
                active_workspace_id=workspace_id,
                source_version=2,
            )
            self._write(next_state)
            return self._catalog(next_state)

    async def add_mount(
        self,
        workspace_id: str,
        *,
        alias: str,
        root_path: str,
        access_mode: WorkspaceMountAccess,
        enabled: bool,
        expected_revision: int,
    ) -> WorkspaceSummary:
        async with self.mutation_gate.hold():
            state, revision, mounts = self._mount_target(workspace_id)
            self._require_item_revision(revision, expected_revision)
            self._require_not_busy(workspace_id)
            if len(mounts) >= 20:
                raise WorkspaceError(WorkspaceFailure.MOUNT_LIMIT_REACHED)
            normalized_alias = self._mount_alias(alias)
            canonical_root = self._root(root_path)
            self._require_mount_unique(mounts, normalized_alias)
            if enabled:
                self._require_no_overlap(state, canonical_root)
            mount = WorkspaceMountRecord(
                self._new_identifier(), normalized_alias, canonical_root, self._access(access_mode), enabled
            )
            next_mounts = (*mounts, mount)
            self._require_mount_budget(next_mounts)
            next_state = self._replace_mounts(state, workspace_id, next_mounts)
            self._write(next_state)
            return self._summary_for_state(next_state, workspace_id)

    async def update_mount(
        self,
        workspace_id: str,
        mount_id: str,
        *,
        alias: str,
        root_path: str,
        access_mode: WorkspaceMountAccess,
        enabled: bool,
        expected_revision: int,
    ) -> WorkspaceSummary:
        async with self.mutation_gate.hold():
            state, revision, mounts = self._mount_target(workspace_id)
            self._require_item_revision(revision, expected_revision)
            self._require_not_busy(workspace_id)
            current = next((item for item in mounts if item.id == mount_id), None)
            if current is None:
                raise WorkspaceError(WorkspaceFailure.MOUNT_NOT_FOUND)
            normalized_alias = self._mount_alias(alias)
            if (
                not enabled
                and self._root_policy.comparison_key(root_path)
                == self._root_policy.comparison_key(current.root_path)
            ):
                canonical_root = current.root_path
            else:
                canonical_root = self._root(root_path)
            self._require_mount_unique(mounts, normalized_alias, excluding=mount_id)
            if enabled:
                self._require_no_overlap(state, canonical_root, excluding_mount=mount_id)
            updated = WorkspaceMountRecord(
                current.id, normalized_alias, canonical_root, self._access(access_mode), enabled
            )
            next_mounts = tuple(updated if item.id == mount_id else item for item in mounts)
            self._require_mount_budget(next_mounts)
            next_state = self._replace_mounts(state, workspace_id, next_mounts)
            self._write(next_state)
            return self._summary_for_state(next_state, workspace_id)

    async def delete_mount(
        self, workspace_id: str, mount_id: str, *, expected_revision: int
    ) -> WorkspaceSummary:
        async with self.mutation_gate.hold():
            state, revision, mounts = self._mount_target(workspace_id)
            self._require_item_revision(revision, expected_revision)
            self._require_not_busy(workspace_id)
            if not any(item.id == mount_id for item in mounts):
                raise WorkspaceError(WorkspaceFailure.MOUNT_NOT_FOUND)
            next_state = self._replace_mounts(
                state,
                workspace_id,
                tuple(item for item in mounts if item.id != mount_id),
            )
            self._write(next_state)
            return self._summary_for_state(next_state, workspace_id)

    def execution_context(self, workspace_id: str) -> WorkspaceExecutionContext:
        state = self._state()
        summary = (
            self._default_summary(state)
            if workspace_id == DEFAULT_WORKSPACE_ID
            else self._summary(self._find(state, workspace_id))
        )
        mounts = tuple(
            WorkspaceMountExecutionContext(
                item.id,
                item.alias,
                item.root_path,
                item.root_hash,
                item.access_mode,
                item.enabled,
                item.availability,
                item.unavailable_reason,
            )
            for item in summary.mounts
        )
        return WorkspaceExecutionContext(
            id=summary.id,
            kind=summary.kind,
            name=summary.name,
            root_path=summary.root_path,
            revision=summary.revision,
            root_hash=_root_hash(summary.root_path),
            availability=summary.availability,
            unavailable_reason=summary.unavailable_reason,
            directory_name=summary.directory_name,
            mounts=mounts,
            mount_manifest_hash=_mount_manifest_hash(mounts),
        )

    def _catalog(self, state: WorkspaceCatalogState) -> WorkspaceCatalog:
        summaries = [self._default_summary(state)]
        summaries.extend(self._summary(item) for item in state.workspaces)
        return WorkspaceCatalog(state.revision, state.active_workspace_id, tuple(summaries))

    def _default_summary(self, state: WorkspaceCatalogState) -> WorkspaceSummary:
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        root = self._managed_path(DEFAULT_WORKSPACE_DIRECTORY)
        status = self._root_policy.inspect_saved_root(str(root))
        return WorkspaceSummary(
            DEFAULT_WORKSPACE_ID,
            WorkspaceKind.DEFAULT,
            DEFAULT_WORKSPACE_NAME,
            DEFAULT_WORKSPACE_DIRECTORY,
            str(root),
            status.availability,
            status.unavailable_reason,
            self._mount_summaries(state.default_mounts),
            state.default_revision,
            epoch,
            state.default_updated_at,
            self._usage_for(DEFAULT_WORKSPACE_ID),
        )

    def _summary(self, item: WorkspaceRecord) -> WorkspaceSummary:
        root = self._managed_path(item.directory_name)
        status = self._root_policy.inspect_saved_root(str(root))
        return WorkspaceSummary(
            item.id,
            WorkspaceKind.MANAGED,
            item.name,
            item.directory_name,
            str(root),
            status.availability,
            status.unavailable_reason,
            self._mount_summaries(item.mounts),
            item.revision,
            item.created_at,
            item.updated_at,
            self._usage_for(item.id),
        )

    def _mount_summaries(
        self, mounts: tuple[WorkspaceMountRecord, ...]
    ) -> tuple[WorkspaceMountSummary, ...]:
        results: list[WorkspaceMountSummary] = []
        for item in mounts:
            availability = WorkspaceAvailability.NOT_APPLICABLE
            unavailable_reason = None
            if item.enabled:
                status = self._root_policy.inspect_saved_root(item.root_path)
                availability = status.availability
                unavailable_reason = status.unavailable_reason
            elif item.disabled_reason is not None:
                availability = WorkspaceAvailability.UNAVAILABLE
                unavailable_reason = item.disabled_reason
            results.append(
                WorkspaceMountSummary(
                    item.id,
                    item.alias,
                    item.root_path,
                    _root_hash(item.root_path),
                    item.access_mode,
                    item.enabled,
                    availability,
                    unavailable_reason,
                )
            )
        return tuple(results)

    def _mount_target(
        self, workspace_id: str
    ) -> tuple[WorkspaceCatalogState, int, tuple[WorkspaceMountRecord, ...]]:
        state = self._state()
        if workspace_id == DEFAULT_WORKSPACE_ID:
            return state, state.default_revision, state.default_mounts
        record = self._find(state, workspace_id)
        return state, record.revision, record.mounts

    def _replace_mounts(
        self,
        state: WorkspaceCatalogState,
        workspace_id: str,
        mounts: tuple[WorkspaceMountRecord, ...],
    ) -> WorkspaceCatalogState:
        now = self._now()
        if workspace_id == DEFAULT_WORKSPACE_ID:
            return replace(
                state,
                revision=state.revision + 1,
                default_revision=state.default_revision + 1,
                default_mounts=mounts,
                default_updated_at=now,
                source_version=2,
            )
        current = self._find(state, workspace_id)
        updated = replace(
            current,
            mounts=mounts,
            revision=current.revision + 1,
            updated_at=now,
        )
        return self._replace_record(state, updated)

    def _replace_record(
        self, state: WorkspaceCatalogState, updated: WorkspaceRecord
    ) -> WorkspaceCatalogState:
        return replace(
            state,
            revision=state.revision + 1,
            workspaces=tuple(
                updated if item.id == updated.id else item for item in state.workspaces
            ),
            source_version=2,
        )

    def _summary_for_state(
        self, state: WorkspaceCatalogState, workspace_id: str
    ) -> WorkspaceSummary:
        return (
            self._default_summary(state)
            if workspace_id == DEFAULT_WORKSPACE_ID
            else self._summary(self._find(state, workspace_id))
        )

    def _require_no_overlap(
        self,
        state: WorkspaceCatalogState,
        root: str,
        *,
        excluding_mount: str | None = None,
    ) -> None:
        managed = [str(self._managed_path(DEFAULT_WORKSPACE_DIRECTORY))]
        managed.extend(str(self._managed_path(item.directory_name)) for item in state.workspaces)
        mounted = [
            item
            for item in (*state.default_mounts, *(mount for record in state.workspaces for mount in record.mounts))
            if item.enabled and item.id != excluding_mount
        ]
        if any(WorkspaceRootPolicy.paths_overlap(root, candidate) for candidate in managed):
            raise WorkspaceError(WorkspaceFailure.OVERLAPPING_ROOT)
        if any(WorkspaceRootPolicy.paths_overlap(root, item.root_path) for item in mounted):
            raise WorkspaceError(WorkspaceFailure.OVERLAPPING_ROOT)

    def _require_not_busy(self, workspace_id: str) -> None:
        if self._usage_for(workspace_id).active_run_count:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_BUSY)

    @staticmethod
    def _require_mount_unique(
        mounts: tuple[WorkspaceMountRecord, ...],
        alias: str,
        *,
        excluding: str | None = None,
    ) -> None:
        if any(item.id != excluding and item.alias.casefold() == alias.casefold() for item in mounts):
            raise WorkspaceError(WorkspaceFailure.DUPLICATE_MOUNT_ALIAS)

    @staticmethod
    def _require_mount_budget(mounts: tuple[WorkspaceMountRecord, ...]) -> None:
        if sum(len(item.alias) + len(item.root_path) for item in mounts) > 12_000:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)

    def _require_unique_name_and_directory(
        self,
        state: WorkspaceCatalogState,
        name: str,
        directory: str,
        *,
        excluding: str | None = None,
    ) -> None:
        if excluding != DEFAULT_WORKSPACE_ID and name.casefold() == DEFAULT_WORKSPACE_NAME.casefold():
            raise WorkspaceError(WorkspaceFailure.DUPLICATE_NAME)
        if excluding != DEFAULT_WORKSPACE_ID and directory.casefold() == DEFAULT_WORKSPACE_DIRECTORY.casefold():
            raise WorkspaceError(WorkspaceFailure.MANAGED_ROOT_EXISTS)
        for item in state.workspaces:
            if item.id == excluding:
                continue
            if item.name.casefold() == name.casefold():
                raise WorkspaceError(WorkspaceFailure.DUPLICATE_NAME)
            if item.directory_name.casefold() == directory.casefold():
                raise WorkspaceError(WorkspaceFailure.MANAGED_ROOT_EXISTS)

    def _state(self) -> WorkspaceCatalogState:
        try:
            state = self._store.get()
        except WorkspaceStoreError:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE) from None
        if state.source_version == 2:
            self._validate_persisted_overlaps(state)
        return state

    def _write(self, state: WorkspaceCatalogState) -> None:
        try:
            self._store.set(state)
        except WorkspaceStoreError:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE) from None

    def _managed_path(self, directory_name: str) -> Path:
        path = (self._managed_root / directory_name).resolve(strict=False)
        if path.parent != self._managed_root:
            raise WorkspaceError(WorkspaceFailure.INVALID_DIRECTORY_NAME)
        return path

    def _disable_legacy_managed_overlaps(
        self, state: WorkspaceCatalogState
    ) -> WorkspaceCatalogState:
        managed = [str(self._managed_path(DEFAULT_WORKSPACE_DIRECTORY))]
        managed.extend(str(self._managed_path(item.directory_name)) for item in state.workspaces)
        records = tuple(
            replace(
                item,
                mounts=tuple(
                    replace(
                        mount,
                        enabled=False,
                        disabled_reason=WorkspaceUnavailableReason.OVERLAP,
                    )
                    if mount.enabled
                    and any(
                        WorkspaceRootPolicy.paths_overlap(mount.root_path, root)
                        for root in managed
                    )
                    else mount
                    for mount in item.mounts
                ),
            )
            for item in state.workspaces
        )
        return replace(state, workspaces=records)

    def _validate_persisted_overlaps(self, state: WorkspaceCatalogState) -> None:
        managed = [str(self._managed_path(DEFAULT_WORKSPACE_DIRECTORY))]
        managed.extend(str(self._managed_path(item.directory_name)) for item in state.workspaces)
        mounted: list[str] = []
        for mount in (*state.default_mounts, *(child for item in state.workspaces for child in item.mounts)):
            if not mount.enabled:
                continue
            if any(WorkspaceRootPolicy.paths_overlap(mount.root_path, root) for root in managed):
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)
            if any(WorkspaceRootPolicy.paths_overlap(mount.root_path, root) for root in mounted):
                raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)
            mounted.append(mount.root_path)

    @staticmethod
    def _ensure_directory(path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
            if not path.is_dir() or path.is_symlink():
                raise OSError
        except OSError:
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
            or any(
                unicodedata.category(character) in {"Cc", "Cf"}
                for character in normalized
            )
        ):
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        return normalized

    @staticmethod
    def _mount_alias(value: str) -> str:
        if type(value) is not str:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        normalized = unicodedata.normalize("NFC", value).strip()
        if (
            not normalized
            or len(normalized) > 40
            or any(
                unicodedata.category(character) in {"Cc", "Cf"}
                or character in "/\\"
                for character in normalized
            )
        ):
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        return normalized

    @staticmethod
    def _directory_name(value: str) -> str:
        try:
            return WorkspaceRootPolicy.directory_name(value)
        except InvalidWorkspaceDirectoryName:
            raise WorkspaceError(WorkspaceFailure.INVALID_DIRECTORY_NAME) from None

    @staticmethod
    def _safe_directory(value: str) -> bool:
        try:
            WorkspaceRootPolicy.directory_name(value)
            return True
        except InvalidWorkspaceDirectoryName:
            return False

    def _root(self, value: str) -> str:
        try:
            return self._root_policy.validate_new_root(value)
        except UnsafeWorkspaceRoot:
            raise WorkspaceError(WorkspaceFailure.UNSAFE_ROOT) from None
        except InvalidWorkspaceRoot:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST) from None

    @staticmethod
    def _access(value: WorkspaceMountAccess) -> WorkspaceMountAccess:
        if not isinstance(value, WorkspaceMountAccess):
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        return value

    @staticmethod
    def _require_catalog_revision(state: WorkspaceCatalogState, expected: int) -> None:
        if type(expected) is not int or expected < 0:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        if state.revision != expected:
            raise WorkspaceError(WorkspaceFailure.REVISION_CONFLICT)

    @staticmethod
    def _require_item_revision(current: int, expected: int) -> None:
        if type(expected) is not int or expected < 1:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        if current != expected:
            raise WorkspaceError(WorkspaceFailure.REVISION_CONFLICT)

    def _usage_for(self, workspace_id: str) -> WorkspaceUsage:
        try:
            return self._usage.workspace_usage(workspace_id)
        except WorkspaceError:
            raise
        except Exception:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE) from None

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)
        return value.astimezone(timezone.utc)

    def _new_identifier(self) -> str:
        value = self._identifier_factory()
        try:
            parsed = __import__("uuid").UUID(value)
        except (TypeError, ValueError, AttributeError):
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE) from None
        if str(parsed) != value or parsed.version != 4 or value == DEFAULT_WORKSPACE_ID:
            raise WorkspaceError(WorkspaceFailure.WORKSPACE_STORE_UNAVAILABLE)
        return value

    @staticmethod
    def _encode_cursor(directory_name: str) -> str:
        raw = json.dumps([directory_name.casefold(), directory_name], ensure_ascii=False).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(value: str) -> tuple[str, str]:
        try:
            padded = value + "=" * (-len(value) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        except Exception:
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST) from None
        if (
            type(decoded) is not list
            or len(decoded) != 2
            or not all(type(item) is str for item in decoded)
        ):
            raise WorkspaceError(WorkspaceFailure.INVALID_REQUEST)
        return decoded[0], decoded[1]


def _root_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mount_manifest_hash(
    mounts: tuple[WorkspaceMountExecutionContext, ...]
) -> str:
    payload = [
        {
            "id": item.id,
            "alias": item.alias,
            "rootHash": item.root_hash,
            "accessMode": item.access_mode.value,
            "enabled": item.enabled,
            "availability": item.availability.value,
        }
        for item in sorted(mounts, key=lambda item: item.id)
    ]
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
