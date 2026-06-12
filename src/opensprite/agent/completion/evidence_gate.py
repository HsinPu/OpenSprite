"""Deterministic task-contract evidence checks for completion gating."""

from __future__ import annotations

from dataclasses import dataclass

from ..execution import ExecutionResult
from ..task.contract import (
    TaskContract,
    TaskIntent,
    missing_evidence,
    neutral_task_contract,
)

MISSING_TASK_EVIDENCE_REASON = "required task evidence was not produced"


def missing_evidence_active_task_detail(missing_evidence: tuple[str, ...]) -> str | None:
    if not missing_evidence:
        return None
    return "\n".join(f"- {item}" for item in missing_evidence)


@dataclass(frozen=True)
class EvidenceGateResult:
    """Verdict for deterministic task-contract evidence."""

    passed: bool
    task_contract: TaskContract
    missing_evidence: tuple[str, ...] = ()
    reason: str = ""

    @property
    def active_task_detail(self) -> str | None:
        return missing_evidence_active_task_detail(self.missing_evidence)


class EvidenceGateService:
    """Evaluate whether the execution produced required contract evidence."""

    def evaluate(
        self,
        *,
        task_intent: TaskIntent,
        execution_result: ExecutionResult,
        verification_passed: bool,
    ) -> EvidenceGateResult:
        task_contract = execution_result.task_contract or neutral_task_contract(task_intent)
        missing = missing_evidence(
            task_contract,
            tuple(execution_result.tool_evidence or ()),
            file_change_count=execution_result.file_change_count,
            verification_passed=verification_passed,
        )
        if missing:
            return EvidenceGateResult(
                passed=False,
                task_contract=task_contract,
                missing_evidence=missing,
                reason=MISSING_TASK_EVIDENCE_REASON,
            )
        return EvidenceGateResult(passed=True, task_contract=task_contract)
