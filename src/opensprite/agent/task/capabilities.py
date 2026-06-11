"""Task capability, scorecard, and sensor evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal

from ...media import count_media_artifacts
from ...tools.evidence import (
    is_web_source_artifact_kind,
    is_web_source_evidence_tool,
)

if TYPE_CHECKING:
    from ..completion_gate import CompletionGateResult
    from ..execution import ExecutionResult

OPERATIONS_TASK_TYPE = "operations"
MEDIA_EXTRACTION_TASK_TYPE = "media_extraction"
CODE_CHANGE_TASK_TYPE = "code_change"
WORKSPACE_READ_TASK_TYPE = "workspace_read"
WORKSPACE_ANALYSIS_TASK_TYPE = "workspace_analysis"
PURE_ANSWER_TASK_TYPE = "pure_answer"
PLANNING_TASK_TYPE = "planning"
HISTORY_RETRIEVAL_TASK_TYPE = "history_retrieval"
GENERIC_TASK_TYPE = "task"
ANALYSIS_TASK_TYPE = "analysis"
FILE_CHANGE_REQUIREMENT_KIND = "file_change"
VERIFICATION_REQUIREMENT_KIND = "verification"


def is_planning_task_type(task_type: str | None) -> bool:
    return str(task_type or "").strip() == PLANNING_TASK_TYPE


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
SENSOR_OPS_TOOL_SELECTION_BOUNDARY = "ops.tool_selection_boundary"
SENSOR_COMPLETION_OPERATION_REPORT = "completion.operation_report"

SENSOR_IDS_BY_TASK_TYPE: dict[str, tuple[str, ...]] = {
    "conversation": (SENSOR_CHAT_NO_UNEXPECTED_TOOLS, SENSOR_COMPLETION_FINAL_ANSWER),
    "question": (SENSOR_CHAT_NO_UNEXPECTED_TOOLS, SENSOR_COMPLETION_FINAL_ANSWER),
    "pure_answer": (SENSOR_CHAT_NO_UNEXPECTED_TOOLS, SENSOR_COMPLETION_FINAL_ANSWER),
    "web_research": (SENSOR_RESEARCH_SOURCE_COVERAGE, SENSOR_RESEARCH_FRESHNESS, SENSOR_COMPLETION_SOURCE_GROUNDING),
    "workspace_analysis": (SENSOR_CODING_WORKSPACE_EVIDENCE, SENSOR_COMPLETION_VERIFICATION_OR_GAP),
    "code_change": (SENSOR_CODING_FILE_CHANGE, SENSOR_CODING_VERIFICATION, SENSOR_COMPLETION_CHANGE_SUMMARY),
    "media_extraction": (SENSOR_MEDIA_ARTIFACT, SENSOR_COMPLETION_MEDIA_SUMMARY),
    "operations": (SENSOR_OPS_AUDIT_TRACE, SENSOR_OPS_TOOL_SELECTION_BOUNDARY, SENSOR_COMPLETION_OPERATION_REPORT),
}


def expected_sensor_ids_for_task_type(task_type: str) -> tuple[str, ...]:
    """Return the expected sensor ids for one task type."""
    return SENSOR_IDS_BY_TASK_TYPE.get(task_type, ())


TASK_SENSOR_PASS_STATUS = "pass"
TASK_SENSOR_WARN_STATUS = "warn"
TASK_SENSOR_FAIL_STATUS = "fail"
TASK_SENSOR_NOT_APPLICABLE_STATUS = "not_applicable"
TaskCheckStatus = Literal["pass", "warn", "fail", "not_applicable"]


@dataclass(frozen=True)
class TaskSensorResult:
    """One deterministic or inferential task sensor verdict."""

    sensor_id: str
    status: TaskCheckStatus
    summary: str = ""
    details: dict[str, Any] | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-safe sensor result."""
        return {
            "sensor_id": self.sensor_id,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details or {}),
        }


@dataclass(frozen=True)
class TaskScorecard:
    """One compact view of contract, tools, sensors, completion, and trace health."""

    contract: dict[str, Any]
    tools: dict[str, Any]
    tool_selection: dict[str, Any]
    sensors: tuple[TaskSensorResult, ...]
    completion: dict[str, Any]
    trace_health: dict[str, Any]

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-safe scorecard payload."""
        return {
            "schema_version": 1,
            "kind": "task_scorecard",
            "contract": dict(self.contract),
            "tools": dict(self.tools),
            "tool_selection": dict(self.tool_selection),
            "sensors": [sensor.to_metadata() for sensor in self.sensors],
            "completion": dict(self.completion),
            "trace_health": dict(self.trace_health),
        }


def evaluate_task_sensors(
    *,
    task_type: str,
    execution_result: ExecutionResult,
    completion_result: CompletionGateResult,
) -> tuple[TaskSensorResult, ...]:
    """Evaluate the expected sensors for a task type."""
    sensor_ids = expected_sensor_ids_for_task_type(task_type)
    return tuple(
        _evaluate_sensor(sensor_id, execution_result=execution_result, completion_result=completion_result)
        for sensor_id in sensor_ids
    )


def _evaluate_sensor(
    sensor_id: str,
    *,
    execution_result: ExecutionResult,
    completion_result: CompletionGateResult,
) -> TaskSensorResult:
    if sensor_id == SENSOR_CHAT_NO_UNEXPECTED_TOOLS:
        count = execution_result.executed_tool_calls
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if count == 0 else TASK_SENSOR_WARN_STATUS,
            "No tools were needed." if count == 0 else "Conversation turn used tools.",
            {"executed_tool_calls": count},
        )
    if sensor_id == SENSOR_COMPLETION_FINAL_ANSWER:
        return _completion_sensor(sensor_id, completion_result)
    if sensor_id == SENSOR_RESEARCH_SOURCE_COVERAGE:
        count = _artifact_count_matching(execution_result, is_web_source_artifact_kind)
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if count > 0 else TASK_SENSOR_FAIL_STATUS,
            "Traceable web sources were recorded." if count > 0 else "No traceable web source artifact was recorded.",
            {"web_source_artifacts": count},
        )
    if sensor_id == SENSOR_RESEARCH_FRESHNESS:
        evidence_count = _web_tool_evidence_count(execution_result)
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if evidence_count > 0 else TASK_SENSOR_WARN_STATUS,
            "Live web evidence is present." if evidence_count > 0 else "No live web evidence was found.",
            {"web_tool_evidence": evidence_count},
        )
    if sensor_id == SENSOR_COMPLETION_SOURCE_GROUNDING:
        return _missing_evidence_sensor(sensor_id, completion_result)
    if sensor_id == SENSOR_CODING_WORKSPACE_EVIDENCE:
        evidence_count = len(execution_result.tool_evidence)
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if evidence_count > 0 else TASK_SENSOR_WARN_STATUS,
            "Workspace evidence was gathered." if evidence_count > 0 else "No workspace evidence was recorded.",
            {"tool_evidence": evidence_count},
        )
    if sensor_id == SENSOR_CODING_FILE_CHANGE:
        count = execution_result.file_change_count
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if count > 0 else TASK_SENSOR_FAIL_STATUS,
            "File changes were recorded." if count > 0 else "No file changes were recorded.",
            {"file_change_count": count},
        )
    if sensor_id == SENSOR_CODING_VERIFICATION:
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if execution_result.verification_passed else TASK_SENSOR_WARN_STATUS,
            "Verification passed." if execution_result.verification_passed else "Verification did not pass.",
            {
                "verification_attempted": execution_result.verification_attempted,
                "verification_passed": execution_result.verification_passed,
            },
        )
    if sensor_id == SENSOR_COMPLETION_CHANGE_SUMMARY:
        return _completion_sensor(sensor_id, completion_result)
    if sensor_id == SENSOR_COMPLETION_VERIFICATION_OR_GAP:
        return _missing_evidence_sensor(sensor_id, completion_result)
    if sensor_id == SENSOR_MEDIA_ARTIFACT:
        count = count_media_artifacts(execution_result.task_artifacts)
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if count > 0 else TASK_SENSOR_FAIL_STATUS,
            "Media artifacts were recorded." if count > 0 else "No media artifact was recorded.",
            {"media_artifacts": count},
        )
    if sensor_id == SENSOR_COMPLETION_MEDIA_SUMMARY:
        return _completion_sensor(sensor_id, completion_result)
    if sensor_id == SENSOR_OPS_AUDIT_TRACE:
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS if execution_result.executed_tool_calls > 0 else TASK_SENSOR_WARN_STATUS,
            "Operational tool activity was recorded." if execution_result.executed_tool_calls > 0 else "No operational tool activity was recorded.",
            {"executed_tool_calls": execution_result.executed_tool_calls},
        )
    if sensor_id == SENSOR_OPS_TOOL_SELECTION_BOUNDARY:
        return TaskSensorResult(
            sensor_id,
            TASK_SENSOR_PASS_STATUS,
            "Tool selection metadata was recorded.",
            {"has_tool_selection": bool(execution_result.tool_selection)},
        )
    if sensor_id == SENSOR_COMPLETION_OPERATION_REPORT:
        return _completion_sensor(sensor_id, completion_result)
    return TaskSensorResult(sensor_id, TASK_SENSOR_NOT_APPLICABLE_STATUS, "No deterministic check is defined.")


def _completion_sensor(sensor_id: str, completion_result: CompletionGateResult) -> TaskSensorResult:
    from ..completion_gate import is_complete_completion_status

    complete = is_complete_completion_status(completion_result.status)
    return TaskSensorResult(
        sensor_id,
        TASK_SENSOR_PASS_STATUS if complete else TASK_SENSOR_FAIL_STATUS,
        completion_result.reason,
        {"status": completion_result.status},
    )


def _missing_evidence_sensor(sensor_id: str, completion_result: CompletionGateResult) -> TaskSensorResult:
    missing = tuple(completion_result.missing_evidence)
    return TaskSensorResult(
        sensor_id,
        TASK_SENSOR_PASS_STATUS if not missing else TASK_SENSOR_FAIL_STATUS,
        "No missing evidence." if not missing else "Completion gate reported missing evidence.",
        {"missing_evidence": list(missing)},
    )


def _artifact_count_matching(execution_result: ExecutionResult, matches_kind: Callable[[str | None], bool]) -> int:
    return sum(1 for artifact in execution_result.task_artifacts if matches_kind(artifact.kind))


def _web_tool_evidence_count(execution_result: ExecutionResult) -> int:
    return sum(1 for evidence in execution_result.tool_evidence if is_web_source_evidence_tool(evidence.name))
