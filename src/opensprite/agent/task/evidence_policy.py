"""Evidence and acceptance policy helpers for task contracts."""

from __future__ import annotations

from typing import Any

from ...tools.evidence import (
    SOURCE_ARTIFACT_CRITERION_KIND,
    SOURCE_DETAIL_CRITERION_KIND,
    SOURCE_REFERENCE_CRITERION_KIND,
    ToolEvidence,
)
from ...tool_names import WORKSPACE_WRITE_TOOL_NAMES
from .capabilities import CODE_CHANGE_TASK_TYPE, FILE_CHANGE_REQUIREMENT_KIND
from .contract import (
    ALL_RESOURCE_COVERAGE,
    ITEMIZED_OUTPUT_CRITERION_KIND,
    MEDIA_ARTIFACT_CRITERION_KIND,
    OPERATION_REPORT_CRITERION_KIND,
    REQUIRED_TOOL_EVIDENCE_KIND,
    RESOURCE_COVERAGE_REQUIREMENT_KIND,
    SUBSTANTIVE_FINAL_ANSWER_CRITERION_KIND,
    VERIFICATION_OR_GAP_CRITERION_KIND,
    VERIFICATION_REQUIREMENT_KIND,
    WORKSPACE_LOCATION_CRITERION_KIND,
)
from .resources import ResourceIndex

FILE_CHANGE_TASK_TYPES = frozenset({CODE_CHANGE_TASK_TYPE})


def contract_has_acceptance_criterion(task_contract: Any, *kinds: str) -> bool:
    if task_contract is None:
        return False
    normalized = {str(kind or "") for kind in kinds if str(kind or "")}
    if not normalized:
        return False
    return any(_criterion_kind(criterion) in normalized for criterion in getattr(task_contract, "acceptance_criteria", ()) or ())


def contract_requests_itemized_output(task_contract: Any) -> bool:
    return contract_has_acceptance_criterion(task_contract, ITEMIZED_OUTPUT_CRITERION_KIND)


def contract_requests_source_reference(task_contract: Any) -> bool:
    return contract_has_acceptance_criterion(task_contract, SOURCE_REFERENCE_CRITERION_KIND)


def contract_requests_source_material(task_contract: Any) -> bool:
    return contract_has_acceptance_criterion(
        task_contract,
        SOURCE_ARTIFACT_CRITERION_KIND,
        SOURCE_DETAIL_CRITERION_KIND,
    )


def contract_requests_substantive_final_answer(task_contract: Any) -> bool:
    return contract_has_acceptance_criterion(task_contract, SUBSTANTIVE_FINAL_ANSWER_CRITERION_KIND)


def is_itemized_output_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == ITEMIZED_OUTPUT_CRITERION_KIND


def is_substantive_final_answer_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == SUBSTANTIVE_FINAL_ANSWER_CRITERION_KIND


def is_source_artifact_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == SOURCE_ARTIFACT_CRITERION_KIND


def is_source_detail_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == SOURCE_DETAIL_CRITERION_KIND


def is_source_reference_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == SOURCE_REFERENCE_CRITERION_KIND


def is_workspace_location_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == WORKSPACE_LOCATION_CRITERION_KIND


def is_media_artifact_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == MEDIA_ARTIFACT_CRITERION_KIND


def is_verification_or_gap_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == VERIFICATION_OR_GAP_CRITERION_KIND


def is_operation_report_criterion(criterion: Any) -> bool:
    return _criterion_kind(criterion) == OPERATION_REPORT_CRITERION_KIND


def missing_evidence(
    contract: Any,
    evidence: tuple[ToolEvidence, ...],
    *,
    file_change_count: int,
    verification_passed: bool,
) -> tuple[str, ...]:
    """Return human-readable missing evidence items for a contract."""
    if contract is None:
        return ()
    missing: list[str] = []
    ok_evidence = [item for item in evidence if item.ok]
    aliases = ResourceIndex.aliases_for(getattr(contract, "selected_resources", ()) or ())
    for requirement in getattr(contract, "requirements", ()) or ():
        requirement_kind = _requirement_attr(requirement, "kind")
        if requirement_kind == REQUIRED_TOOL_EVIDENCE_KIND:
            tools = frozenset(_requirement_tools(requirement))
            count = sum(1 for item in ok_evidence if item.name in tools)
            if count < max(1, requirement.min_count):
                missing.append(requirement.description or f"Use one of: {', '.join(sorted(tools))}")
        elif requirement_kind == RESOURCE_COVERAGE_REQUIREMENT_KIND:
            tools = frozenset(_requirement_tools(requirement))
            covered = {
                alias
                for item in ok_evidence
                if item.name in tools
                for resource_id in item.resource_ids
                for alias in aliases.get(resource_id, {resource_id})
            }
            required = set(requirement.resource_ids)
            if _requirement_attr(requirement, "coverage") == ALL_RESOURCE_COVERAGE:
                uncovered = tuple(resource_id for resource_id in requirement.resource_ids if resource_id not in covered)
                if uncovered:
                    missing.append(f"Missing resource coverage for: {', '.join(uncovered)}")
            elif len(covered & required) < max(1, requirement.min_count):
                missing.append(requirement.description or "Missing required resource coverage.")
        elif (
            requirement_kind == FILE_CHANGE_REQUIREMENT_KIND
            and file_change_count < max(1, requirement.min_count)
        ):
            missing.append(requirement.description or "Record a workspace file change.")
        elif requirement_kind == VERIFICATION_REQUIREMENT_KIND and not verification_passed:
            missing.append(requirement.description or "Record passing verification evidence.")
    return tuple(missing)


def contract_expects_file_change(task_contract: Any) -> bool:
    """Return whether a task contract requires workspace file changes."""
    task_type = str(getattr(task_contract, "task_type", "") or "")
    if task_type in FILE_CHANGE_TASK_TYPES:
        return True
    for requirement in getattr(task_contract, "requirements", ()) or ():
        if _requirement_attr(requirement, "kind") == FILE_CHANGE_REQUIREMENT_KIND:
            return True
    return any(
        _policy_value(tool_name) in WORKSPACE_WRITE_TOOL_NAMES
        for tool_name in getattr(task_contract, "required_tools", ()) or ()
    )


def _criterion_kind(criterion: Any) -> str:
    return str(getattr(criterion, "kind", "") or "")


def _requirement_attr(requirement: Any, attr: str) -> str:
    return str(getattr(requirement, attr, "") or "")


def _requirement_tools(requirement: Any) -> tuple[str, ...]:
    raw_tools = getattr(requirement, "tools", ()) or ()
    if isinstance(raw_tools, str):
        raw_tools = (raw_tools,)
    tools: list[str] = []
    for value in raw_tools:
        tool_name = _policy_value(value)
        if tool_name and tool_name not in tools:
            tools.append(tool_name)
    return tuple(tools)


def _policy_value(value: object) -> str:
    return str(value or "").strip().lower()
