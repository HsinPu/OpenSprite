"""Contract evidence checks for one agent turn."""

from __future__ import annotations

from dataclasses import dataclass

from .execution import ExecutionResult
from .task_contract import TaskContract, missing_evidence, neutral_task_contract
from .task_intent import TaskIntent


@dataclass(frozen=True)
class EvidenceGateResult:
    """Verdict for deterministic task-contract evidence."""

    passed: bool
    task_contract: TaskContract
    missing_evidence: tuple[str, ...] = ()
    reason: str = ""

    @property
    def active_task_detail(self) -> str | None:
        if not self.missing_evidence:
            return None
        return "\n".join(f"- {item}" for item in self.missing_evidence)


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
                reason="required task evidence was not produced",
            )
        return EvidenceGateResult(passed=True, task_contract=task_contract)
