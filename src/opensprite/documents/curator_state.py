"""Persistent state storage for background curator runs."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from ..utils.log import logger


CURATOR_STATE_SCHEMA_VERSION = 1
CURATOR_HISTORY_LIMIT = 20


def default_curator_state() -> dict[str, Any]:
    return {
        "schema_version": CURATOR_STATE_SCHEMA_VERSION,
        "paused": False,
        "run_count": 0,
        "last_run_at": None,
        "last_run_duration_seconds": None,
        "last_run_summary": None,
        "last_run_jobs": [],
        "last_run_changed": [],
        "last_run_failed": [],
        "last_run_slow": [],
        "last_run_job_results": [],
        "last_run_status": None,
        "last_error": None,
        "history": [],
    }


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def dict_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def normalize_curator_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    state = default_curator_state()
    state["paused"] = bool(raw.get("paused"))
    state["run_count"] = safe_int(raw.get("run_count"))
    state["last_run_at"] = raw.get("last_run_at")
    state["last_run_duration_seconds"] = raw.get("last_run_duration_seconds")
    state["last_run_summary"] = raw.get("last_run_summary")
    state["last_error"] = raw.get("last_error")
    state["last_run_status"] = raw.get("last_run_status")
    state["last_run_jobs"] = string_list(raw.get("last_run_jobs"))
    state["last_run_changed"] = string_list(raw.get("last_run_changed"))
    state["last_run_failed"] = string_list(raw.get("last_run_failed"))
    state["last_run_slow"] = string_list(raw.get("last_run_slow"))
    state["last_run_job_results"] = dict_list(raw.get("last_run_job_results"))
    state["history"] = dict_list(raw.get("history"))[-CURATOR_HISTORY_LIMIT:]
    return state


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
            return dict(state) if isinstance(state, dict) else default_curator_state()
        if not state_path.exists():
            return default_curator_state()
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("curator.state.load_failed | path=%s error=%s", state_path, exc)
            return default_curator_state()
        return normalize_curator_state(raw if isinstance(raw, dict) else None)

    def save(self, session_id: str, state: dict[str, Any]) -> None:
        state_path = self.state_file_for_session(session_id)
        normalized_state = normalize_curator_state(state)
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
