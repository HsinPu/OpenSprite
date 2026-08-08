"""Curator state defaults and normalization policy."""

from __future__ import annotations

from typing import Any


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
