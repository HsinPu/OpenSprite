"""Agent-owned data contracts for delegated child-task state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoredDelegatedTask:
    """Delegated child-task status attached to one parent run."""

    task_id: str
    prompt_type: str | None = None
    status: str = "unknown"
    selected: bool = False
    summary: str = ""
    error: str = ""
    child_session_id: str | None = None
    last_child_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable payload for run metadata and APIs."""
        return {
            "task_id": self.task_id,
            "prompt_type": self.prompt_type,
            "status": self.status,
            "selected": self.selected,
            "summary": self.summary,
            "error": self.error,
            "child_session_id": self.child_session_id,
            "last_child_run_id": self.last_child_run_id,
            "metadata": dict(self.metadata or {}),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def selected_delegated_task(tasks: tuple[StoredDelegatedTask, ...]) -> StoredDelegatedTask | None:
    """Return the selected delegated task, if any."""
    for task in tasks:
        if task.selected:
            return task
    return None
