"""Scope helpers for curator maintenance runs."""

from __future__ import annotations


CURATOR_MAINTENANCE_JOB_KEYS = ("memory", "recent_summary", "user_profile")
CURATOR_SCOPE_CHOICES = ("maintenance", "skills", *CURATOR_MAINTENANCE_JOB_KEYS)


def _ordered_maintenance_job_keys(job_keys: tuple[str, ...] | list[str] | set[str]) -> tuple[str, ...]:
    requested = {str(item or "").strip() for item in job_keys if str(item or "").strip()}
    return tuple(job_key for job_key in CURATOR_MAINTENANCE_JOB_KEYS if job_key in requested)


def resolve_curator_scope(scope: str | None) -> tuple[tuple[str, ...], bool]:
    normalized = str(scope or "").strip().lower()
    if not normalized:
        return CURATOR_MAINTENANCE_JOB_KEYS, True
    if normalized == "maintenance":
        return CURATOR_MAINTENANCE_JOB_KEYS, False
    if normalized == "skills":
        return (), True
    if normalized in CURATOR_MAINTENANCE_JOB_KEYS:
        return (normalized,), False
    raise ValueError(f"Unknown curator scope: {normalized}")
