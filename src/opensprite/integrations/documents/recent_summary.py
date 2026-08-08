"""Filesystem persistence for per-session recent summaries."""

from __future__ import annotations

from pathlib import Path

from ..workspace.paths import (
    get_session_recent_summary_file,
    get_session_recent_summary_state_file,
)
from .progress_state import JsonProgressStore as _JsonProgressStore


class RecentSummaryStore:
    """Persist RECENT_SUMMARY.md files and their incremental state."""

    def __init__(
        self,
        memory_dir: Path,
        *,
        app_home: str | Path | None = None,
        workspace_root: str | Path | None = None,
    ):
        self.memory_dir = Path(memory_dir).expanduser()
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.app_home = Path(app_home).expanduser() if app_home is not None else None
        self.workspace_root = Path(workspace_root).expanduser() if workspace_root is not None else None
        if self.app_home is None and self.workspace_root is None:
            raise ValueError("RecentSummaryStore requires app_home or workspace_root for session-scoped paths")

    def _get_summary_file(self, session_id: str) -> Path:
        summary_file = get_session_recent_summary_file(
            session_id,
            workspace_root=self.workspace_root,
            app_home=self.app_home,
        )
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        return summary_file

    def _state_store(self, session_id: str) -> _JsonProgressStore:
        return _JsonProgressStore(
            get_session_recent_summary_state_file(
                session_id,
                workspace_root=self.workspace_root,
                app_home=self.app_home,
            )
        )

    def read(self, session_id: str) -> str:
        summary_file = self._get_summary_file(session_id)
        if summary_file.exists():
            return summary_file.read_text(encoding="utf-8")
        return ""

    def write(self, session_id: str, content: str) -> None:
        self._get_summary_file(session_id).write_text(content, encoding="utf-8")

    def get_context(self, session_id: str) -> str:
        summary = self.read(session_id)
        if summary:
            return f"# Recent Summary\n\n{summary}"
        return ""

    def get_processed_index(self, session_id: str) -> int:
        return self._state_store(session_id).get_processed_index(session_id)

    def set_processed_index(self, session_id: str, index: int) -> None:
        self._state_store(session_id).set_processed_index(session_id, index)

    def clear(self, session_id: str) -> None:
        summary_file = self._get_summary_file(session_id)
        if summary_file.exists():
            summary_file.unlink()
        self._state_store(session_id).set_processed_index(session_id, 0)
