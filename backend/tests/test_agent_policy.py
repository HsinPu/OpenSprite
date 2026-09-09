"""Workspace shadowing must be identical for discovery and spawning."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from opensprite_backend.custom_agents.definition import parse_agent_definition
from opensprite_backend.custom_agents.models import AgentCandidate, AgentError, AgentRecord
from opensprite_backend.custom_agents.policy import execution_snapshot, resolve_agents


def candidate(name="review", *, workspace=None, enabled=True, error=None, parsed_name=None):
    import json

    content = f'name = {json.dumps(parsed_name or name)}\ndescription = "Review"\ndeveloper_instructions = "Return evidence"\n'
    return AgentCandidate(
        AgentRecord(id=str(uuid4()), scope="workspace" if workspace else "global", workspaceId=workspace,
                    fileName=f"agent-{uuid4()}.toml", name=name, revision=1, enabled=enabled),
        None if error else parse_agent_definition(content.encode()), error,
    )


@pytest.mark.parametrize("error,enabled", [(None, True), (None, False), ("missing", True), ("invalid_format", True), ("workspace_unavailable", True)])
def test_local_registration_shadows_global_without_fallback(error, enabled):
    workspace = str(uuid4())
    global_agent = candidate("Review")
    local = candidate("review", workspace=workspace, error=error, enabled=enabled)
    decisions = resolve_agents((global_agent, local), workspace, enabled=True)
    assert decisions[0].reason == "shadowed_by_workspace"
    assert decisions[0].shadowed_by == local.record.id
    snapshot = execution_snapshot(decisions)
    with pytest.raises(AgentError, match="agent_unavailable"):
        snapshot.get(global_agent.record.id)
    assert len(snapshot.available) == (1 if enabled and error is None else 0)


def test_removing_local_restores_global_and_other_workspace_does_not_shadow():
    workspace = str(uuid4())
    global_agent = candidate()
    other = candidate(workspace=str(uuid4()))
    assert execution_snapshot(resolve_agents((global_agent, other), workspace, enabled=True)).available == (global_agent,)


def test_current_parsed_name_is_used_and_collision_fails_all_candidates():
    workspace = str(uuid4())
    first = candidate("old", parsed_name="REVIEW", workspace=workspace)
    second = candidate("review", workspace=workspace)
    decisions = resolve_agents((first, second), workspace, enabled=True)
    assert [item.reason for item in decisions] == ["duplicate_name", "duplicate_name"]
    assert not execution_snapshot(decisions).available


def test_unicode_names_are_normalized_for_shadowing():
    workspace = str(uuid4())
    global_agent = candidate("Café")
    local = candidate("local", workspace=workspace, parsed_name="Cafe\u0301")
    decisions = resolve_agents((global_agent, local), workspace, enabled=True)
    assert decisions[0].reason == "shadowed_by_workspace"
    assert execution_snapshot(decisions).available == (local,)


def test_master_switch_and_independent_local_switch():
    workspace = str(uuid4())
    local = candidate(workspace=workspace)
    disabled_global = candidate(enabled=False)
    assert execution_snapshot(resolve_agents((disabled_global, local), workspace, enabled=True)).available == (local,)
    assert not execution_snapshot(resolve_agents((disabled_global, local), workspace, enabled=False)).available


def test_snapshot_stays_immutable_after_policy_change():
    workspace = str(uuid4())
    original = candidate()
    snapshot = execution_snapshot(resolve_agents((original,), workspace, enabled=True))
    resolve_agents((original,), workspace, enabled=False)
    assert snapshot.get(original.record.id) is original
    with pytest.raises(FrozenInstanceError):
        snapshot.available = ()
