"""Filesystem-backed persistence for the session learning ledger."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from opensprite.core.logging import logger

_SCHEMA_VERSION = 1


class JsonLearningLedgerStore:
    """Read and write versioned learning-ledger entries as JSON."""

    def __init__(
        self,
        *,
        state_path: str | Path | None = None,
        state_path_for_session: Callable[[str], str | Path] | None = None,
    ):
        if (state_path is None) == (state_path_for_session is None):
            raise ValueError("Provide exactly one learning-ledger path source")
        self._state_path = Path(state_path).expanduser() if state_path is not None else None
        self._state_path_for_session = state_path_for_session

    def _state_file_for_session(self, session_id: str) -> Path:
        if self._state_path_for_session is not None:
            return Path(self._state_path_for_session(session_id)).expanduser()
        assert self._state_path is not None
        return self._state_path

    def load_entries(self, session_id: str) -> list[dict[str, Any]]:
        state_path = self._state_file_for_session(session_id)
        if not state_path.exists():
            return []
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("learning.state.load_failed | path=%s error=%s", state_path, exc)
            return []
        if not isinstance(raw, dict):
            return []
        raw_entries = raw.get("entries") if isinstance(raw.get("entries"), list) else []
        return [dict(entry) for entry in raw_entries if isinstance(entry, dict)]

    def save_entries(self, session_id: str, entries: list[dict[str, Any]]) -> None:
        state_path = self._state_file_for_session(session_id)
        stored_entries = [dict(entry) for entry in entries if isinstance(entry, dict)]
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(state_path.parent),
                prefix=f".{state_path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(
                        {"schema_version": _SCHEMA_VERSION, "entries": stored_entries},
                        handle,
                        indent=2,
                        sort_keys=True,
                        ensure_ascii=False,
                    )
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
            logger.warning("learning.state.save_failed | path=%s error=%s", state_path, exc)

    def clear_session(self, session_id: str) -> None:
        state_path = self._state_file_for_session(session_id)
        try:
            if state_path.exists():
                state_path.unlink()
        except OSError as exc:
            logger.warning("learning.state.delete_failed | path=%s error=%s", state_path, exc)
