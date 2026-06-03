"""Shared policy helpers for deterministic evidence-gate failures."""

from __future__ import annotations


MISSING_TASK_EVIDENCE_REASON = "required task evidence was not produced"


def missing_evidence_active_task_detail(missing_evidence: tuple[str, ...]) -> str | None:
    if not missing_evidence:
        return None
    return "\n".join(f"- {item}" for item in missing_evidence)
