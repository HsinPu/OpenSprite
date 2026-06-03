"""Canonical inventory of harness profiles, policies, and expected sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .harness_policy import HarnessPolicyService
from .harness_profile import HarnessProfile, preview_harness_profiles


SENSOR_CHAT_NO_UNEXPECTED_TOOLS = "chat.no_unexpected_tools"
SENSOR_COMPLETION_FINAL_ANSWER = "completion.final_answer"
SENSOR_RESEARCH_SOURCE_COVERAGE = "research.source_coverage"
SENSOR_RESEARCH_FRESHNESS = "research.freshness"
SENSOR_COMPLETION_SOURCE_GROUNDING = "completion.source_grounding"
SENSOR_CODING_WORKSPACE_EVIDENCE = "coding.workspace_evidence"
SENSOR_CODING_FILE_CHANGE = "coding.file_change"
SENSOR_CODING_VERIFICATION = "coding.verification"
SENSOR_COMPLETION_CHANGE_SUMMARY = "completion.change_summary"
SENSOR_COMPLETION_VERIFICATION_OR_GAP = "completion.verification_or_gap"
SENSOR_MEDIA_ARTIFACT = "media.artifact"
SENSOR_COMPLETION_MEDIA_SUMMARY = "completion.media_summary"
SENSOR_OPS_AUDIT_TRACE = "ops.audit_trace"
SENSOR_OPS_APPROVAL_BOUNDARY = "ops.approval_boundary"
SENSOR_COMPLETION_OPERATION_REPORT = "completion.operation_report"

SENSOR_IDS_BY_TASK_TYPE: dict[str, tuple[str, ...]] = {
    "conversation": (SENSOR_CHAT_NO_UNEXPECTED_TOOLS, SENSOR_COMPLETION_FINAL_ANSWER),
    "question": (SENSOR_CHAT_NO_UNEXPECTED_TOOLS, SENSOR_COMPLETION_FINAL_ANSWER),
    "pure_answer": (SENSOR_CHAT_NO_UNEXPECTED_TOOLS, SENSOR_COMPLETION_FINAL_ANSWER),
    "web_research": (SENSOR_RESEARCH_SOURCE_COVERAGE, SENSOR_RESEARCH_FRESHNESS, SENSOR_COMPLETION_SOURCE_GROUNDING),
    "workspace_analysis": (SENSOR_CODING_WORKSPACE_EVIDENCE, SENSOR_COMPLETION_VERIFICATION_OR_GAP),
    "workspace_change": (SENSOR_CODING_FILE_CHANGE, SENSOR_CODING_VERIFICATION, SENSOR_COMPLETION_CHANGE_SUMMARY),
    "media_extraction": (SENSOR_MEDIA_ARTIFACT, SENSOR_COMPLETION_MEDIA_SUMMARY),
    "operations": (SENSOR_OPS_AUDIT_TRACE, SENSOR_OPS_APPROVAL_BOUNDARY, SENSOR_COMPLETION_OPERATION_REPORT),
}


@dataclass(frozen=True)
class HarnessInventoryItem:
    """One representative harness shape used for scoring, UI, and evals."""

    key: str
    profile: HarnessProfile
    policy_name: str
    expected_sensor_ids: tuple[str, ...]

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-safe inventory entry."""
        return {
            "key": self.key,
            "profile": self.profile.to_metadata(),
            "policy_name": self.policy_name,
            "expected_sensor_ids": list(self.expected_sensor_ids),
        }


def build_harness_inventory() -> tuple[HarnessInventoryItem, ...]:
    """Return the canonical harness inventory derived from preview profiles."""
    policy_service = HarnessPolicyService()
    items: list[HarnessInventoryItem] = []
    for profile in preview_harness_profiles():
        policy = policy_service.select(profile)
        items.append(
            HarnessInventoryItem(
                key=f"{profile.name}:{profile.task_type}",
                profile=profile,
                policy_name=policy.name,
                expected_sensor_ids=SENSOR_IDS_BY_TASK_TYPE[profile.task_type],
            )
        )
    return tuple(items)


def expected_sensor_ids_for_task_type(task_type: str) -> tuple[str, ...]:
    """Return the expected sensor ids for one harness task type."""
    return SENSOR_IDS_BY_TASK_TYPE.get(task_type, ())


def harness_inventory_payload() -> dict[str, Any]:
    """Return a stable payload for debug exports, evals, and future UI wiring."""
    items = build_harness_inventory()
    return {
        "schema_version": 1,
        "kind": "harness_inventory",
        "items": [item.to_metadata() for item in items],
    }
