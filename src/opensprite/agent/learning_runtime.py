"""Agent learning ledger runtime helpers."""

from __future__ import annotations

from typing import Any

from ..tool_names import READ_SKILL_TOOL_NAME
from ..utils.log import logger


def record_learning(
    agent: Any,
    session_id: str,
    *,
    kind: str,
    target_id: str,
    summary: str,
    source_run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist one learned artifact into the session learning ledger."""
    if agent.learning_ledger is None:
        return
    agent.learning_ledger.record_learning(
        session_id,
        kind=kind,
        target_id=target_id,
        summary=summary,
        source_run_id=source_run_id,
        metadata=metadata,
    )


def skill_description(agent: Any, skill_name: str, session_id: str) -> str:
    """Return the best available description for one skill in the current session scope."""
    skills_loader = getattr(agent._context_builder, "skills_loader", None)
    session_skills_dir_resolver = getattr(agent._context_builder, "get_session_skills_dir", None)
    if skills_loader is None or not callable(session_skills_dir_resolver):
        return ""
    try:
        session_skills_dir = session_skills_dir_resolver(session_id)
        for skill in skills_loader.get_skills(session_skills_dir):
            if skill.name == skill_name:
                return str(skill.description or "").strip()
    except Exception:
        logger.exception("[%s] learning.skill-metadata.failed | skill=%s", session_id, skill_name)
    return ""


def finalize_learning_reuse(agent: Any, session_id: str, run_id: str, success: bool) -> None:
    """Mark any skills read during one run as reused in the learning ledger."""
    skill_names = sorted(agent._run_skill_reads.pop(run_id, set()))
    if not skill_names or agent.learning_ledger is None:
        return
    outcome = "success" if success else "failed"
    for skill_name in skill_names:
        description = skill_description(agent, skill_name, session_id)
        summary = description or f"Skill '{skill_name}' was reused by the agent."
        metadata = {"source": READ_SKILL_TOOL_NAME, "skill_name": skill_name}
        if description:
            metadata["description"] = description
        agent.learning_ledger.mark_used(
            session_id,
            kind="skill",
            target_id=skill_name,
            outcome=outcome,
            summary=summary,
            source_run_id=run_id,
            metadata=metadata,
        )
