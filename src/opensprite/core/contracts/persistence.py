"""Framework-independent records exchanged with persistence providers."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoredMessage:
    """One persisted conversation message."""

    role: str
    content: str
    timestamp: float
    tool_name: str | None = None
    is_consolidated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoredRun:
    """Persisted execution run for one user-facing turn."""

    run_id: str
    session_id: str
    status: str
    created_at: float
    updated_at: float
    finished_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoredRunEvent:
    """One structured event emitted while a run is executing."""

    run_id: str
    session_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    event_id: int | None = None


@dataclass
class StoredRunPart:
    """One durable, ordered execution artifact for a run."""

    run_id: str
    session_id: str
    part_type: str
    content: str = ""
    tool_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    part_id: int | None = None


@dataclass
class StoredRunFileChange:
    """One file mutation captured during a run for later inspection."""

    run_id: str
    session_id: str
    tool_name: str
    path: str
    action: str
    before_sha256: str | None = None
    after_sha256: str | None = None
    before_content: str | None = None
    after_content: str | None = None
    diff: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    change_id: int | None = None


@dataclass
class StoredRunTrace:
    """Complete persisted execution trace for one run."""

    run: StoredRun
    events: list[StoredRunEvent] = field(default_factory=list)
    parts: list[StoredRunPart] = field(default_factory=list)
    file_changes: list[StoredRunFileChange] = field(default_factory=list)


@dataclass
class StoredBackgroundProcess:
    """Persisted metadata for one managed background shell process."""

    process_session_id: str
    owner_session_id: str
    command: str
    state: str
    started_at: float
    updated_at: float
    owner_run_id: str | None = None
    owner_channel: str | None = None
    owner_external_chat_id: str | None = None
    pid: int | None = None
    cwd: str | None = None
    termination_reason: str | None = None
    exit_code: int | None = None
    notify_mode: str = "agent_summary"
    output_tail: str = ""
    output_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    finished_at: float | None = None
