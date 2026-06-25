"""Curator request and maintenance job definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..agent.execution import ExecutionResult


SnapshotReader = Callable[[str], str]
SessionRunner = Callable[[str], Awaitable[Any]]


@dataclass(frozen=True)
class CuratorRequest:
    """Latest pending background curation request for one session."""

    session_id: str
    run_id: str | None = None
    channel: str | None = None
    external_chat_id: str | None = None
    result: ExecutionResult | None = None
    maintenance_job_keys: tuple[str, ...] = ()
    run_skill_review: bool = False


@dataclass(frozen=True)
class CuratorJob:
    """One snapshot-backed background job."""

    key: str
    label: str
    snapshot_reader: SnapshotReader
    runner: SessionRunner


@dataclass(frozen=True)
class CuratorMaintenanceServices:
    """Maintenance services that run after a visible assistant turn."""

    maybe_consolidate_memory: SessionRunner
    maybe_update_recent_summary: SessionRunner
    maybe_update_user_profile: SessionRunner
    maybe_update_active_task: SessionRunner
    read_memory_snapshot: SnapshotReader
    read_recent_summary_snapshot: SnapshotReader
    read_user_profile_snapshot: SnapshotReader
    read_active_task_snapshot: SnapshotReader

    def jobs(self) -> tuple[CuratorJob, ...]:
        """Return maintenance jobs in the canonical post-turn order."""
        return (
            CuratorJob("memory", "memory", self.read_memory_snapshot, self.maybe_consolidate_memory),
            CuratorJob(
                "recent_summary",
                "recent summary",
                self.read_recent_summary_snapshot,
                self.maybe_update_recent_summary,
            ),
            CuratorJob(
                "user_profile",
                "user profile",
                self.read_user_profile_snapshot,
                self.maybe_update_user_profile,
            ),
            CuratorJob(
                "active_task",
                "active task",
                self.read_active_task_snapshot,
                self.maybe_update_active_task,
            ),
        )
