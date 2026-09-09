"""Real Agent context assembly with a deterministic gateway."""
import asyncio
import pytest
from uuid import uuid4
from opensprite_backend.skills.models import SkillContent, SkillExecutionSnapshot
from opensprite_backend.skills.execution import SkillRunState
from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.conversations.models import RunStatus, RunEventType
from opensprite_backend.inference.models import ModelToolCall, ModelCompleted, ModelFinishReason, ModelTextDelta
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.tools.policy import ReadOnlyToolPolicy
from context_test_support import TestCapabilityResolver
from test_agent_loop import store, accepted_run, ScriptedGateway, LookupTool
from opensprite_backend.tools.definition import ToolDefinition, ToolEffect


def snapshot():
    return SkillExecutionSnapshot((SkillContent(str(uuid4()), "global", "Review", "Review code", 1, "a" * 64, "UNIQUE_FULL_INSTRUCTIONS"),))


@pytest.mark.parametrize("count", [64, 65, 131])
def test_large_tool_catalog_reaches_gateway_with_skills(tmp_path, count):
    async def scenario():
        repository = store(tmp_path)
        run = accepted_run(repository)
        skills = snapshot()
        tools = [LookupTool(definition=ToolDefinition(
            name=f"lookup_{i:03}", description="Look up a note.",
            input_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            effect=ToolEffect.READ_ONLY,
        )) for i in range(count - 2)]
        gateway = ScriptedGateway([
            [ModelToolCall("load", "load_skill", {"skillId": skills.available[0].id}),
             ModelCompleted(ModelFinishReason.TOOL_CALLS)],
            [ModelToolCall("lookup", "lookup_000", {}), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
            [ModelTextDelta("Done"), ModelCompleted(ModelFinishReason.FINAL)],
        ])
        loop = AgentLoop(repository=repository, gateway=gateway,
                         tools=ToolRegistry(tools, policy=ReadOnlyToolPolicy()),
                         capability_resolver=TestCapabilityResolver())
        result = await loop.execute(run.id, asyncio.Event(), skills=skills)
        assert result.status is RunStatus.COMPLETED
        assert len(gateway.requests) == 3
        expected = sorted([tool.definition.name for tool in tools] + ["discover_skills", "load_skill"])
        assert all([tool.name for tool in request.tools] == expected for request in gateway.requests)
        assert tools[0].calls == [{}]
        events = repository.list_run_events(run.id, after_sequence=0, limit=100)
        assert all(event.data["toolNames"] == expected for event in events if event.type is RunEventType.MODEL_STARTED)
    asyncio.run(scenario())


def test_discovery_shrinks_to_budget_without_skipping_items():
    import json
    from opensprite_backend.agent.skill_phase import handle_skill_call
    from opensprite_backend.agent.context.counter import ConservativeTokenCounter
    from opensprite_backend.inference.models import ModelMessage

    async def scenario():
        state = SkillRunState(SkillExecutionSnapshot(tuple(
            SkillContent(str(uuid4()), "global", f"Skill {i}", "x" * 512, 1, "a" * 64, "body") for i in range(20))))
        counter = ConservativeTokenCounter()
        transcript = [ModelMessage(role="system", content="base")]
        _, messages = await handle_skill_call(
            call=ModelToolCall("discover", "discover_skills", {"query": "", "offset": 0}),
            skill_state=state, base_system_prompt="base", system_prompt="base", transcript=transcript,
            tool_definitions=(), input_budget_tokens=1000, counter=counter, repository=None, run_id="unused")
        page = json.loads(messages[-1].content)
        assert 0 < len(page["items"]) < 20
        assert page["nextOffset"] == len(page["items"])
        assert counter.request(tuple(messages), ()) <= 1000
        following = state.discover({"query": "", "offset": page["nextOffset"]})
        assert following["items"][0]["id"] == state.snapshot.available[len(page["items"])].id
        assert not state.loaded
    asyncio.run(scenario())


def test_lazy_load_only_injects_after_selection(tmp_path):
    async def scenario():
        repository = store(tmp_path)
        run = accepted_run(repository)
        skills = snapshot()
        call = lambda i: ModelToolCall(i, "load_skill", {"skillId": skills.available[0].id})
        gateway = ScriptedGateway([[call("one"), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
                                   [call("two"), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
                                   [ModelTextDelta("Done"), ModelCompleted(ModelFinishReason.FINAL)]])
        loop = AgentLoop(repository=repository, gateway=gateway, tools=ToolRegistry([], policy=ReadOnlyToolPolicy()),
                         capability_resolver=TestCapabilityResolver())
        result = await loop.execute(run.id, asyncio.Event(), skills=skills)
        assert result.status is RunStatus.COMPLETED
        assert "UNIQUE_FULL_INSTRUCTIONS" not in gateway.requests[0].messages[0].content
        assert "UNIQUE_FULL_INSTRUCTIONS" in gateway.requests[1].messages[0].content
        assert {tool.name for tool in gateway.requests[0].tools} == {"load_skill", "discover_skills"}
        assert sum(event.type is RunEventType.SKILL_LOADED for event in repository.list_run_events(run.id, after_sequence=0, limit=100)) == 1
    asyncio.run(scenario())


def test_manual_state_does_not_change_snapshot():
    skills = snapshot()
    state = SkillRunState(skills)
    state.loaded = state.candidate(skills.available[0].id)
    assert not SkillRunState(skills).loaded
    assert "UNIQUE_FULL_INSTRUCTIONS" in state.prompt("Base")


def test_discovery_pages_all_items_without_eager_descriptions():
    contents = tuple(SkillContent(str(uuid4()), "global", f"Skill {i}", "unique description " + "x" * 900,
                                  1, "a" * 64, "body") for i in range(57))
    state = SkillRunState(SkillExecutionSnapshot(contents))
    assert "unique description" not in state.prompt("Base")
    ids = []
    offset = 0
    while offset is not None:
        page = state.discover({"query": "", "offset": offset})
        assert len(page["items"]) <= 20
        assert all(item["descriptionTruncated"] for item in page["items"])
        ids.extend(item["id"] for item in page["items"])
        offset = page["nextOffset"]
    assert ids == [item.id for item in contents]
    assert not state.loaded
    assert state.discover({"query": "SKILL 56", "offset": 0})["items"][0]["id"] == contents[-1].id


def test_agent_discovers_before_loading(tmp_path):
    async def scenario():
        repository = store(tmp_path)
        run = accepted_run(repository)
        skills = snapshot()
        gateway = ScriptedGateway([
            [ModelToolCall("search", "discover_skills", {"query": "review", "offset": 0}), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
            [ModelToolCall("load", "load_skill", {"skillId": skills.available[0].id}), ModelCompleted(ModelFinishReason.TOOL_CALLS)],
            [ModelTextDelta("Done"), ModelCompleted(ModelFinishReason.FINAL)]])
        loop = AgentLoop(repository=repository, gateway=gateway, tools=ToolRegistry([], policy=ReadOnlyToolPolicy()), capability_resolver=TestCapabilityResolver())
        assert (await loop.execute(run.id, asyncio.Event(), skills=skills)).status is RunStatus.COMPLETED
        assert "Review code" not in gateway.requests[0].messages[0].content
        assert "Review code" in gateway.requests[1].messages[-1].content
        assert "UNIQUE_FULL_INSTRUCTIONS" in gateway.requests[2].messages[0].content
    asyncio.run(scenario())


def test_manual_instructions_in_first_request_and_event(tmp_path):
    async def scenario():
        repository = store(tmp_path)
        run = accepted_run(repository)
        available = snapshot().available
        skills = SkillExecutionSnapshot(available, (available[0].id,))
        gateway = ScriptedGateway([[ModelTextDelta("Done"), ModelCompleted(ModelFinishReason.FINAL)]])
        loop = AgentLoop(repository=repository, gateway=gateway, tools=ToolRegistry([], policy=ReadOnlyToolPolicy()), capability_resolver=TestCapabilityResolver())
        assert (await loop.execute(run.id, asyncio.Event(), skills=skills)).status is RunStatus.COMPLETED
        assert "UNIQUE_FULL_INSTRUCTIONS" in gateway.requests[0].messages[0].content
        events = repository.list_run_events(run.id, after_sequence=0, limit=100)
        loaded = [event for event in events if event.type is RunEventType.SKILL_LOADED]
        assert len(loaded) == 1
        assert loaded[0].data["source"] == "manual"
        assert "UNIQUE_FULL_INSTRUCTIONS" not in str(events)
    asyncio.run(scenario())


def test_skill_limit_and_unknown_id_do_not_mutate_state():
    import pytest
    from opensprite_backend.skills.models import SkillError
    contents = tuple(snapshot().available[0] for _ in range(6))
    state = SkillRunState(SkillExecutionSnapshot(contents))
    for item in contents[:5]:
        state.loaded = state.candidate(item.id)
    before = state.loaded
    with pytest.raises(SkillError, match="limit_reached"):
        state.candidate(contents[5].id)
    with pytest.raises(SkillError, match="skill_unavailable"):
        state.candidate("../SKILL.md")
    assert state.loaded == before


def test_event_migration_preserves_rows_and_rolls_back(tmp_path):
    import sqlite3
    from contextlib import closing
    import pytest
    from opensprite_backend.conversations.skill_event_migration import migrate

    class InjectedFailure(sqlite3.Connection):
        fail = False
        def execute(self, sql, *args):
            if self.fail and sql.startswith("INSERT INTO run_events SELECT"):
                raise sqlite3.OperationalError("injected")
            return super().execute(sql, *args)

    database = tmp_path / "migration.sqlite"
    with closing(sqlite3.connect(database, factory=InjectedFailure)) as connection:
        connection.executescript("CREATE TABLE runs(id TEXT PRIMARY KEY); CREATE TABLE run_events(run_id TEXT, sequence INTEGER, type TEXT, payload_json TEXT, created_at TEXT); INSERT INTO runs VALUES ('one'); INSERT INTO run_events VALUES ('one',1,'run.started','{}','2026-09-06'); PRAGMA user_version=13;")
        baseline = connection.execute("SELECT * FROM run_events").fetchall()
        connection.fail = True
        with pytest.raises(sqlite3.OperationalError):
            migrate(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 13
        assert connection.execute("SELECT * FROM run_events").fetchall() == baseline
        connection.fail = False
        migrate(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 14
        assert connection.execute("SELECT * FROM run_events").fetchall() == baseline
