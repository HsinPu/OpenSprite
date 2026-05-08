"""Response quality checks for one agent turn."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .execution import ExecutionResult
from .task_intent import TaskIntent


@dataclass(frozen=True)
class QualityGateResult:
    """Verdict for deterministic response-quality checks."""

    passed: bool
    reason: str = ""
    status: str = "complete"


class QualityGateService:
    """Evaluate answer-shape quality rules that are independent of tool evidence."""

    def evaluate(
        self,
        *,
        task_intent: TaskIntent,
        response_text: str,
        execution_result: ExecutionResult,
    ) -> QualityGateResult:
        if execution_result.executed_tool_calls == 0 and _looks_like_missing_requested_items(
            task_intent,
            response_text,
        ):
            return QualityGateResult(
                passed=False,
                status="incomplete",
                reason="assistant did not provide the requested itemized result",
            )
        return QualityGateResult(passed=True)


def _looks_like_missing_requested_items(task_intent: TaskIntent, response_text: str) -> bool:
    requested_count = _requested_item_count(task_intent.objective)
    if requested_count < 3:
        return False
    normalized = re.sub(r"\s+", " ", (response_text or "").strip())
    if not normalized or len(normalized) > 260:
        return False
    return _response_item_count(response_text) < min(requested_count, 3)


def _requested_item_count(objective: str) -> int:
    counts = [int(match) for match in re.findall(r"(?<!\d)\d{1,3}(?!\d)", str(objective or ""))]
    return max(counts, default=0)


def _response_item_count(response_text: str) -> int:
    lines = [line.strip() for line in str(response_text or "").splitlines() if line.strip()]
    item_like = 0
    for line in lines:
        if re.match(r"^(?:[-*]|\d+[.)]|\|)", line):
            item_like += 1
    return item_like
