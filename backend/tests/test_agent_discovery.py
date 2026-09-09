"""Role discovery is paged, snapshot-only, and does not expose instructions."""

import pytest

from opensprite_backend.custom_agents.discovery import discover_agents, discovery_prompt
from opensprite_backend.custom_agents.models import AgentError, AgentExecutionSnapshot
from test_agent_policy import candidate


def test_discovery_pages_without_instructions_or_paths():
    snapshot = AgentExecutionSnapshot(tuple(candidate(f"role-{i}") for i in range(25)))
    first = discover_agents(snapshot, {"query": "", "offset": 0})
    assert len(first["items"]) == 20 and first["nextOffset"] == 20 and first["total"] == 25
    second = discover_agents(snapshot, {"query": "", "offset": 20})
    assert len(second["items"]) == 5 and second["nextOffset"] is None
    assert set(first["items"][0]) == {"id", "name", "scope", "description", "descriptionTruncated"}
    assert "Return evidence" not in str(first)
    assert "role-0" not in discovery_prompt(snapshot)


def test_discovery_search_normalizes_unicode():
    snapshot = AgentExecutionSnapshot((candidate("Café"),))
    assert discover_agents(snapshot, {"query": "CAFE\u0301", "offset": 0})["total"] == 1
    assert discover_agents(snapshot, {"query": "unrelated", "offset": 0})["total"] == 0
    assert discovery_prompt(AgentExecutionSnapshot()) == ""


@pytest.mark.parametrize("arguments", [{}, {"query": "", "offset": True}, {"query": "", "offset": -1}, {"query": "", "offset": 0, "path": "secret"}, {"query": "x" * 201, "offset": 0}])
def test_discovery_rejects_invalid_arguments(arguments):
    with pytest.raises(AgentError, match="invalid_request"):
        discover_agents(AgentExecutionSnapshot(), arguments)
