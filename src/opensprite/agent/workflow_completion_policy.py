"""Shared workflow completion and follow-up routing policy."""

from __future__ import annotations

from .workflow_fields import (
    WORKFLOW_NEXT_STEP_ID_FIELD,
    WORKFLOW_NEXT_STEP_LABEL_FIELD,
    WORKFLOW_NEXT_STEP_PROMPT_TYPE_FIELD,
)
from .workflows import (
    BUGFIX_THEN_TEST_THEN_REVIEW_WORKFLOW_ID,
    IMPLEMENT_THEN_REVIEW_WORKFLOW_ID,
    RESEARCH_THEN_OUTLINE_WORKFLOW_ID,
    REVIEW_WORKFLOW_IDS,
)


WORKFLOW_FIX_STEPS = {
    IMPLEMENT_THEN_REVIEW_WORKFLOW_ID: {
        WORKFLOW_NEXT_STEP_ID_FIELD: "implement",
        WORKFLOW_NEXT_STEP_LABEL_FIELD: "Implement",
        WORKFLOW_NEXT_STEP_PROMPT_TYPE_FIELD: "implementer",
    },
    BUGFIX_THEN_TEST_THEN_REVIEW_WORKFLOW_ID: {
        WORKFLOW_NEXT_STEP_ID_FIELD: "bugfix",
        WORKFLOW_NEXT_STEP_LABEL_FIELD: "Bug fix",
        WORKFLOW_NEXT_STEP_PROMPT_TYPE_FIELD: "bug-fixer",
    },
}
WORKFLOW_VERIFICATION_EVIDENCE_MISSING_REASON = "workflow completed but required verification evidence is still missing"
WORKFLOW_REVIEW_EVIDENCE_MISSING_DETAIL = (
    "Run or rerun a delegated review step for the changed code before treating the workflow as complete."
)
TASK_REVIEW_EVIDENCE_MISSING_DETAIL = (
    "Run or rerun a delegated review step for the changed code before treating the task as complete."
)
TASK_REVIEW_FINDINGS_FOLLOW_UP_DETAIL = (
    "Address the delegated review findings before treating the task as complete."
)


def workflow_unsuccessful_reason(workflow_id: str | None) -> str:
    return f"workflow {str(workflow_id or '').strip()} did not complete successfully"


def workflow_review_evidence_missing_reason(workflow_id: str | None) -> str:
    return f"workflow {str(workflow_id or '').strip()} completed but review evidence is missing"


def workflow_review_findings_follow_up_reason(workflow_id: str | None) -> str:
    return f"workflow {str(workflow_id or '').strip()} completed but review findings still require follow-up"


def workflow_clean_review_reason(workflow_id: str | None) -> str:
    return f"workflow {str(workflow_id or '').strip()} completed with clean review evidence"


def workflow_completed_all_steps_reason(workflow_id: str | None) -> str:
    return f"workflow {str(workflow_id or '').strip()} completed all required steps"


def workflow_review_evidence_missing_detail() -> str:
    return WORKFLOW_REVIEW_EVIDENCE_MISSING_DETAIL


def task_review_evidence_missing_detail() -> str:
    return TASK_REVIEW_EVIDENCE_MISSING_DETAIL


def task_review_findings_follow_up_detail() -> str:
    return TASK_REVIEW_FINDINGS_FOLLOW_UP_DETAIL


def is_research_then_outline_workflow(workflow_id: str | None) -> bool:
    return str(workflow_id or "").strip() == RESEARCH_THEN_OUTLINE_WORKFLOW_ID


def is_review_workflow(workflow_id: str | None) -> bool:
    return str(workflow_id or "").strip() in REVIEW_WORKFLOW_IDS


def workflow_review_follow_up_fields(workflow_id: str | None) -> dict[str, str]:
    if is_review_workflow(workflow_id):
        return {
            WORKFLOW_NEXT_STEP_ID_FIELD: "review",
            WORKFLOW_NEXT_STEP_LABEL_FIELD: "Code review",
            WORKFLOW_NEXT_STEP_PROMPT_TYPE_FIELD: "code-reviewer",
        }
    return {}


def workflow_fix_follow_up_fields(workflow_id: str | None) -> dict[str, str]:
    return dict(WORKFLOW_FIX_STEPS.get(str(workflow_id or "").strip(), {}))
