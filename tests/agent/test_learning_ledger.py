import asyncio
import json

from agent_test_helpers import FakeContextBuilder, make_agent_loop
from opensprite.app.agent import learning_runtime
from opensprite.integrations.workspace.paths import get_session_learning_state_file
from opensprite.integrations.documents.learning import JsonLearningLedgerStore
from opensprite.modules.documents.learning import LearningLedger


def test_agent_loop_marks_read_skill_reuse_in_learning_ledger(tmp_path):
    async def scenario():
        agent = make_agent_loop(tmp_path)
        hook = agent.agent_run_hooks.make_tool_result_hook(
            channel="telegram",
            external_chat_id="room-1",
            session_id="telegram:room-1",
            run_id="run-1",
            enabled=False,
        )
        assert hook is not None
        await hook("read_skill", {"skill_name": "pytest-helper"}, "Skill body")
        learning_runtime.finalize_learning_reuse(agent, "telegram:room-1", "run-1", True)
        return agent.learning_ledger.recent_entries("telegram:room-1", limit=1)

    entries = asyncio.run(scenario())

    assert entries[0]["kind"] == "skill"
    assert entries[0]["target_id"] == "pytest-helper"
    assert entries[0]["use_count"] == 1
    assert entries[0]["last_outcome"] == "success"


def test_agent_loop_ignores_failed_read_skill_for_learning_ledger(tmp_path):
    async def scenario():
        agent = make_agent_loop(tmp_path)
        hook = agent.agent_run_hooks.make_tool_result_hook(
            channel="telegram",
            external_chat_id="room-1",
            session_id="telegram:room-1",
            run_id="run-1",
            enabled=False,
        )
        assert hook is not None
        result = json.dumps({"ok": False, "error": "skill missing"})
        await hook("read_skill", {"skill_name": "pytest-helper"}, result)
        learning_runtime.finalize_learning_reuse(agent, "telegram:room-1", "run-1", True)
        return agent.learning_ledger.recent_entries("telegram:room-1", limit=1)

    entries = asyncio.run(scenario())

    assert entries == []


def test_agent_loop_composes_file_backed_learning_ledger(tmp_path):
    class RecordingContextBuilder(FakeContextBuilder):
        def set_learning_ledger(self, ledger):
            self.attached_learning_ledger = ledger

    app_home = tmp_path / "home"
    workspace_root = tmp_path / "workspace"
    session_id = "telegram:room-1"
    context_builder = RecordingContextBuilder(
        tmp_path / "context",
        app_home=app_home,
        tool_workspace=workspace_root,
    )
    agent = make_agent_loop(
        tmp_path / "context",
        context_builder=context_builder,
    )

    assert context_builder.attached_learning_ledger is agent.learning_ledger
    agent.learning_ledger.record_learning(
        session_id,
        kind="skill",
        target_id="pytest-helper",
        summary="Persisted through AgentLoop composition.",
    )

    state_path = get_session_learning_state_file(
        session_id,
        app_home=app_home,
        workspace_root=workspace_root,
    )
    assert state_path.exists()
    reloaded = LearningLedger(store=JsonLearningLedgerStore(state_path=state_path))
    assert reloaded.recent_entries(session_id, limit=1)[0]["target_id"] == "pytest-helper"
