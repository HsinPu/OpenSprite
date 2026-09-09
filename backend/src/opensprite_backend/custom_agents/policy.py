"""One effective-policy decision shared by management and execution."""

from collections import Counter

from .models import AgentCandidate, AgentDecision, AgentExecutionSnapshot


def resolve_agents(
    candidates: tuple[AgentCandidate, ...],
    workspace_id: str,
    *,
    enabled: bool,
) -> tuple[AgentDecision, ...]:
    """A local registration shadows global even when it cannot execute."""
    relevant = tuple(item for item in candidates if item.record.scope == "global" or item.record.workspaceId == workspace_id)
    counts = Counter((item.record.scope, item.name_key) for item in relevant)
    local: dict[str, list[str]] = {}
    for item in relevant:
        if item.record.scope == "workspace":
            local.setdefault(item.name_key, []).append(item.record.id)
    result = []
    for item in relevant:
        shadows = local.get(item.name_key, []) if item.record.scope == "global" else []
        shadowed_by = shadows[0] if len(shadows) == 1 else None
        if shadows:
            reason = "shadowed_by_workspace"
        elif not enabled:
            reason = "master_disabled"
        elif counts[(item.record.scope, item.name_key)] > 1:
            reason = "duplicate_name"
        elif not item.record.enabled:
            reason = "disabled"
        elif item.error is not None:
            reason = item.error
        elif item.definition is None:
            reason = "invalid_format"
        else:
            reason = "effective"
        result.append(AgentDecision(item, reason, shadowed_by))
    return tuple(result)


def execution_snapshot(decisions: tuple[AgentDecision, ...]) -> AgentExecutionSnapshot:
    return AgentExecutionSnapshot(tuple(item.candidate for item in decisions if item.reason == "effective"))
