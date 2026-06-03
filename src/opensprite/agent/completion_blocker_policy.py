"""Policy helpers for completion-blocker fallback responses."""

from __future__ import annotations

from dataclasses import dataclass

from .completion_gate import CompletionGateResult


@dataclass(frozen=True)
class CompletionBlockerMessages:
    intro: str
    reason_prefix: str
    detail_header: str
    missing_evidence_header: str
    stop_notice: str


def completion_blocker_response(
    completion_result: CompletionGateResult,
    messages: CompletionBlockerMessages,
) -> str:
    reason = (completion_result.reason or completion_result.status or "completion gate did not pass").strip()
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
