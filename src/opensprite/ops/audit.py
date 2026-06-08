"""Operation audit snapshots for high-risk settings changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class OperationAuditRecord:
    operation_type: str
    target: str
    before: dict[str, Any]
    after: dict[str, Any]
    validation: dict[str, Any] = field(default_factory=dict)
    rollback_available: bool = False
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str = ""
    run_id: str = ""
    task_type: str = "operations"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_metadata(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "target": self.target,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "task_type": self.task_type,
            "before": self.before,
            "after": self.after,
            "validation": self.validation,
            "rollback_available": self.rollback_available,
            "created_at": self.created_at,
        }
