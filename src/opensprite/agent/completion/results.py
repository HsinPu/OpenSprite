"""Completion gate result models and metadata field names."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .status import INCOMPLETE_COMPLETION_STATUS

COMPLETION_RESULT_SCHEMA_VERSION_FIELD = "schema_version"
COMPLETION_RESULT_STATUS_FIELD = "status"
COMPLETION_RESULT_REASON_FIELD = "reason"
COMPLETION_RESULT_SHOULD_UPDATE_ACTIVE_TASK_FIELD = "should_update_active_task"
COMPLETION_RESULT_VERIFICATION_REQUIRED_FIELD = "verification_required"
COMPLETION_RESULT_VERIFICATION_ATTEMPTED_FIELD = "verification_attempted"
COMPLETION_RESULT_VERIFICATION_PASSED_FIELD = "verification_passed"
COMPLETION_RESULT_REVIEW_REQUIRED_FIELD = "review_required"
COMPLETION_RESULT_REVIEW_ATTEMPTED_FIELD = "review_attempted"
COMPLETION_RESULT_REVIEW_PASSED_FIELD = "review_passed"
COMPLETION_RESULT_REVIEW_SUMMARY_FIELD = "review_summary"
COMPLETION_RESULT_REVIEW_PROMPT_TYPES_FIELD = "review_prompt_types"
COMPLETION_RESULT_REVIEW_FINDING_COUNT_FIELD = "review_finding_count"
COMPLETION_RESULT_FILE_CHANGE_REQUIRED_FIELD = "file_change_required"
COMPLETION_RESULT_MISSING_EVIDENCE_FIELD = "missing_evidence"
COMPLETION_RESULT_PROGRESS_ONLY_RESPONSE_FIELD = "progress_only_response"
COMPLETION_RESULT_ACTIVE_TASK_STATUS_FIELD = "active_task_status"
COMPLETION_RESULT_ACTIVE_TASK_DETAIL_FIELD = "active_task_detail"
COMPLETION_RESULT_FOLLOW_UP_WORKFLOW_FIELD = "follow_up_workflow"
COMPLETION_RESULT_FOLLOW_UP_STEP_ID_FIELD = "follow_up_step_id"
COMPLETION_RESULT_FOLLOW_UP_STEP_LABEL_FIELD = "follow_up_step_label"
COMPLETION_RESULT_FOLLOW_UP_PROMPT_TYPE_FIELD = "follow_up_prompt_type"
COMPLETION_RESULT_VERIFICATION_ACTION_FIELD = "verification_action"
COMPLETION_RESULT_VERIFICATION_PATH_FIELD = "verification_path"
COMPLETION_RESULT_VERIFICATION_PYTEST_ARGS_FIELD = "verification_pytest_args"
COMPLETION_RESULT_VERIFIER_FIELD = "verifier"
COMPLETION_RESULT_CONFIDENCE_FIELD = "confidence"
COMPLETION_RESULT_ISSUES_FIELD = "issues"
COMPLETION_RESULT_NEXT_ACTION_FIELD = "next_action"
COMPLETION_RESULT_NEXT_PROMPT_FIELD = "next_prompt"
COMPLETION_GATE_DID_NOT_PASS_REASON = "completion gate did not pass"


@dataclass(frozen=True)
class CompletionBlockerMessages:
    intro: str
    reason_prefix: str
    detail_header: str
    missing_evidence_header: str
    stop_notice: str


@dataclass(frozen=True)
class CompletionGateResult:
    """Structured verdict about whether one turn completed the active objective."""

    status: str
    reason: str
    confidence: float = 0.0
    issues: tuple[str, ...] = ()
    next_action: str = ""
    next_prompt: str = ""
    active_task_status: str | None = None
    active_task_detail: str | None = None
    follow_up_workflow: str | None = None
    follow_up_step_id: str | None = None
    follow_up_step_label: str | None = None
    follow_up_prompt_type: str | None = None
    verification_action: str | None = None
    verification_path: str | None = None
    verification_pytest_args: tuple[str, ...] = ()
    should_update_active_task: bool = False
    verification_required: bool = False
    verification_attempted: bool = False
    verification_passed: bool = False
    review_required: bool = False
    review_attempted: bool = False
    review_passed: bool = False
    review_summary: str = ""
    review_prompt_types: tuple[str, ...] = ()
    review_finding_count: int = 0
    file_change_required: bool = False
    missing_evidence: tuple[str, ...] = ()
    progress_only_response: bool = False
    verifier_metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-safe run event payload."""
        payload: dict[str, Any] = {
            COMPLETION_RESULT_SCHEMA_VERSION_FIELD: 1,
            COMPLETION_RESULT_STATUS_FIELD: self.status,
            COMPLETION_RESULT_REASON_FIELD: self.reason,
            COMPLETION_RESULT_SHOULD_UPDATE_ACTIVE_TASK_FIELD: self.should_update_active_task,
            COMPLETION_RESULT_VERIFICATION_REQUIRED_FIELD: self.verification_required,
            COMPLETION_RESULT_VERIFICATION_ATTEMPTED_FIELD: self.verification_attempted,
            COMPLETION_RESULT_VERIFICATION_PASSED_FIELD: self.verification_passed,
            COMPLETION_RESULT_REVIEW_REQUIRED_FIELD: self.review_required,
            COMPLETION_RESULT_REVIEW_ATTEMPTED_FIELD: self.review_attempted,
            COMPLETION_RESULT_REVIEW_PASSED_FIELD: self.review_passed,
            COMPLETION_RESULT_REVIEW_SUMMARY_FIELD: self.review_summary,
            COMPLETION_RESULT_REVIEW_PROMPT_TYPES_FIELD: list(self.review_prompt_types),
            COMPLETION_RESULT_REVIEW_FINDING_COUNT_FIELD: self.review_finding_count,
            COMPLETION_RESULT_FILE_CHANGE_REQUIRED_FIELD: self.file_change_required,
            COMPLETION_RESULT_MISSING_EVIDENCE_FIELD: list(self.missing_evidence),
            COMPLETION_RESULT_PROGRESS_ONLY_RESPONSE_FIELD: self.progress_only_response,
            COMPLETION_RESULT_CONFIDENCE_FIELD: self.confidence,
            COMPLETION_RESULT_ISSUES_FIELD: list(self.issues),
        }
        if self.next_action:
            payload[COMPLETION_RESULT_NEXT_ACTION_FIELD] = self.next_action
        if self.next_prompt:
            payload[COMPLETION_RESULT_NEXT_PROMPT_FIELD] = self.next_prompt
        if self.active_task_status:
            payload[COMPLETION_RESULT_ACTIVE_TASK_STATUS_FIELD] = self.active_task_status
        if self.active_task_detail:
            payload[COMPLETION_RESULT_ACTIVE_TASK_DETAIL_FIELD] = self.active_task_detail
        if self.follow_up_workflow:
            payload[COMPLETION_RESULT_FOLLOW_UP_WORKFLOW_FIELD] = self.follow_up_workflow
        if self.follow_up_step_id:
            payload[COMPLETION_RESULT_FOLLOW_UP_STEP_ID_FIELD] = self.follow_up_step_id
        if self.follow_up_step_label:
            payload[COMPLETION_RESULT_FOLLOW_UP_STEP_LABEL_FIELD] = self.follow_up_step_label
        if self.follow_up_prompt_type:
            payload[COMPLETION_RESULT_FOLLOW_UP_PROMPT_TYPE_FIELD] = self.follow_up_prompt_type
        if self.verification_action:
            payload[COMPLETION_RESULT_VERIFICATION_ACTION_FIELD] = self.verification_action
        if self.verification_path:
            payload[COMPLETION_RESULT_VERIFICATION_PATH_FIELD] = self.verification_path
        if self.verification_pytest_args:
            payload[COMPLETION_RESULT_VERIFICATION_PYTEST_ARGS_FIELD] = list(self.verification_pytest_args)
        if self.verifier_metadata:
            payload[COMPLETION_RESULT_VERIFIER_FIELD] = dict(self.verifier_metadata)
        return payload


def completion_blocker_response(
    completion_result: CompletionGateResult,
    messages: CompletionBlockerMessages,
) -> str:
    reason = (completion_result.reason or completion_result.status or COMPLETION_GATE_DID_NOT_PASS_REASON).strip()
    detail = (completion_result.active_task_detail or "").strip()
    missing = [item.strip() for item in completion_result.missing_evidence if str(item).strip()]
    sections = [
        messages.intro,
        f"{messages.reason_prefix}{reason}",
    ]
    if detail:
        detail_lines = [line.strip("- ").strip() for line in detail.splitlines() if line.strip()]
        if detail_lines:
            sections.append(f"{messages.detail_header}\n" + "\n".join(f"- {line}" for line in detail_lines))
    if missing:
        sections.append(f"{messages.missing_evidence_header}\n" + "\n".join(f"- {item}" for item in missing))
    sections.append(messages.stop_notice)
    return "\n\n".join(sections)
