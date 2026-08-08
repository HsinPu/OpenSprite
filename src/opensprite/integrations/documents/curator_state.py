"""Filesystem-backed persistence for background curator state."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from ...modules.documents.curator_state import (
    default_curator_state as _default_curator_state,
    normalize_curator_state as _normalize_curator_state,
)
from opensprite.core.logging import logger


class CuratorStateStore:
    """Read and write per-session curator state."""

    def __init__(
        self,
        *,
        state_path: Path | None = None,
        state_path_for_session: Callable[[str], Path] | None = None,
    ):
        self._state_path = Path(state_path).expanduser() if state_path is not None else None
        self._state_path_for_session = state_path_for_session
        self._memory_session_states: dict[str, dict[str, Any]] = {}

    def state_file_for_session(self, session_id: str) -> Path | None:
        if self._state_path_for_session is not None:
            return Path(self._state_path_for_session(session_id)).expanduser()
        return self._state_path

    def load(self, session_id: str) -> dict[str, Any]:
        state_path = self.state_file_for_session(session_id)
        if state_path is None:
            state = self._memory_session_states.get(session_id)
            return dict(state) if isinstance(state, dict) else _default_curator_state()
        if not state_path.exists():
            return _default_curator_state()
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("curator.state.load_failed | path=%s error=%s", state_path, exc)
            return _default_curator_state()
        return _normalize_curator_state(raw if isinstance(raw, dict) else None)

    def save(self, session_id: str, state: dict[str, Any]) -> None:
        state_path = self.state_file_for_session(session_id)
        normalized_state = _normalize_curator_state(state)
        if state_path is None:
            self._memory_session_states[session_id] = normalized_state
            return
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(state_path.parent),
                prefix=f".{state_path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(normalized_state, handle, indent=2, sort_keys=True, ensure_ascii=False)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, state_path)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.warning("curator.state.save_failed | path=%s error=%s", state_path, exc)

    def clear(self, session_id: str) -> None:
        self._memory_session_states.pop(session_id, None)
        state_path = self.state_file_for_session(session_id)
        if state_path is None:
            return
        try:
            if state_path.exists():
                state_path.unlink()
        except OSError as exc:
            logger.warning("curator.state.delete_failed | path=%s error=%s", state_path, exc)
