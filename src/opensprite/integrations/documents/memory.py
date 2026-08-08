"""Filesystem persistence for per-session long-term memory."""

from __future__ import annotations

from pathlib import Path

from ..workspace.paths import resolve_session_memory_file
from ...modules.documents.safety import validate_durable_memory_text as _validate_durable_memory_text


class MemoryStore:
    """Persist per-session MEMORY.md files under the configured session tree."""

    def __init__(
        self,
        memory_dir: Path,
        *,
        app_home: str | Path | None = None,
        workspace_root: str | Path | None = None,
    ):
        self.memory_base = Path(memory_dir).expanduser()
        self.memory_base.mkdir(parents=True, exist_ok=True)
        self.app_home = Path(app_home).expanduser() if app_home is not None else None
        self.workspace_root = Path(workspace_root).expanduser() if workspace_root is not None else None
        if self.app_home is None and self.workspace_root is None:
            raise ValueError("MemoryStore requires app_home or workspace_root for session-scoped paths")

    def _memory_file_path(self, session_id: str) -> Path:
        return resolve_session_memory_file(
            session_id,
            workspace_root=self.workspace_root,
            app_home=self.app_home,
        )

    def read(self, session_id: str) -> str:
        memory_file = self._memory_file_path(session_id)
        if memory_file.exists():
            return memory_file.read_text(encoding="utf-8")
        return ""

    def write(self, session_id: str, content: str) -> None:
        _validate_durable_memory_text(content)
        memory_file = self._memory_file_path(session_id)
        memory_file.parent.mkdir(parents=True, exist_ok=True)
        memory_file.write_text(content, encoding="utf-8")

    def get_context(self, session_id: str) -> str:
        memory = self.read(session_id)
        if memory:
            return f"# Long-term Memory\n\n{memory}"
        return ""
