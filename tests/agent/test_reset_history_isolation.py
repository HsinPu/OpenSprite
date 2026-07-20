import asyncio

from agent_test_helpers import FakeContextBuilder, make_agent_loop
from opensprite.context.paths import (
    get_session_curator_state_file,
    get_session_learning_state_file,
    get_session_memory_file,
    get_session_recent_summary_file,
    get_session_skills_dir,
    get_session_workspace,
)
from opensprite.documents.user_profile import create_user_profile_store
from opensprite.documents.recent_summary import RecentSummaryStore
from opensprite.storage.base import StoredMessage
from opensprite.storage.memory import MemoryStorage


class FakeSearchStore:
    def __init__(self):
        self.cleared = []

    async def clear_session(self, session_id: str) -> None:
        self.cleared.append(session_id)


def test_reset_history_only_clears_target_session(tmp_path):
    async def scenario():
        storage = MemoryStorage()
        await storage.add_message("telegram:user-a", StoredMessage(role="user", content="A1", timestamp=1.0))
        await storage.add_message("telegram:user-b", StoredMessage(role="user", content="B1", timestamp=2.0))

        history_search_store = FakeSearchStore()
        agent = make_agent_loop(
            tmp_path,
            storage=storage,
            context_builder=FakeContextBuilder(
                tmp_path,
                app_home=tmp_path / "home",
                tool_workspace=tmp_path / "workspace",
            ),
            history_search_store=history_search_store,
        )

        summary_store = RecentSummaryStore(agent.memory.memory_base, app_home=agent.app_home, workspace_root=agent.tool_workspace)
        summary_store.write("telegram:user-a", "# Active Threads\n- stale context")
        summary_store.write("telegram:user-b", "# Active Threads\n- keep context")
        summary_store.set_processed_index("telegram:user-a", 5)
        summary_store.set_processed_index("telegram:user-b", 7)
        agent.memory.write("telegram:user-a", "memory a")
        agent.memory.write("telegram:user-b", "memory b")
        profile_a = create_user_profile_store(agent.app_home, "telegram:user-a", workspace_root=agent.tool_workspace)
        profile_b = create_user_profile_store(agent.app_home, "telegram:user-b", workspace_root=agent.tool_workspace)
        profile_a.write_managed_block("- likes pytest")
        profile_b.write_managed_block("- likes release notes")
        skills_a = get_session_skills_dir("telegram:user-a", workspace_root=agent.tool_workspace)
        skills_b = get_session_skills_dir("telegram:user-b", workspace_root=agent.tool_workspace)
        (skills_a / "pytest-helper").mkdir(parents=True, exist_ok=True)
        (skills_a / "pytest-helper" / "SKILL.md").write_text("---\nname: pytest-helper\ndescription: helper\n---\nbody\n", encoding="utf-8")
        (skills_b / "release-helper").mkdir(parents=True, exist_ok=True)
        (skills_b / "release-helper" / "SKILL.md").write_text("---\nname: release-helper\ndescription: helper\n---\nbody\n", encoding="utf-8")
        agent.curator.pause("telegram:user-a")
        agent.curator.pause("telegram:user-b")
        agent.learning_ledger.record_learning("telegram:user-a", kind="skill", target_id="pytest-helper", summary="pytest")
        agent.learning_ledger.record_learning("telegram:user-b", kind="skill", target_id="release-helper", summary="release")
        workspace_a = get_session_workspace("telegram:user-a", workspace_root=agent.tool_workspace)
        workspace_b = get_session_workspace("telegram:user-b", workspace_root=agent.tool_workspace)

        await agent.reset_history("telegram:user-a")

        messages_a = await storage.get_messages("telegram:user-a")
        messages_b = await storage.get_messages("telegram:user-b")
        workspace_a_exists = workspace_a.exists()
        workspace_b_exists = workspace_b.exists()
        return {
            "messages_a": messages_a,
            "messages_b": messages_b,
            "cleared": history_search_store.cleared,
            "summary_store": summary_store,
            "workspace_a_exists": workspace_a_exists,
            "workspace_b_exists": workspace_b_exists,
            "memory_a": get_session_memory_file("telegram:user-a", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "memory_b": get_session_memory_file("telegram:user-b", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "summary_a": get_session_recent_summary_file("telegram:user-a", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "summary_b": get_session_recent_summary_file("telegram:user-b", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "curator_state_a": get_session_curator_state_file("telegram:user-a", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "curator_state_b": get_session_curator_state_file("telegram:user-b", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "learning_state_a": get_session_learning_state_file("telegram:user-a", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "learning_state_b": get_session_learning_state_file("telegram:user-b", app_home=agent.app_home, workspace_root=agent.tool_workspace),
            "learning_a": agent.learning_ledger.recent_entries("telegram:user-a"),
            "learning_b": agent.learning_ledger.recent_entries("telegram:user-b"),
            "curator_a": agent.curator.status("telegram:user-a"),
            "curator_b": agent.curator.status("telegram:user-b"),
        }

    result = asyncio.run(scenario())

    assert result["messages_a"] == []
    assert [message.content for message in result["messages_b"]] == ["B1"]
    assert result["cleared"] == ["telegram:user-a"]
    assert result["workspace_a_exists"] is False
    assert result["workspace_b_exists"] is True
    assert result["memory_a"].exists() is False
    assert result["memory_b"].read_text(encoding="utf-8") == "memory b"
    assert result["summary_a"].exists() is False
    assert result["summary_b"].read_text(encoding="utf-8") == "# Active Threads\n- keep context"
    assert result["curator_state_a"].exists() is False
    assert result["curator_state_b"].exists() is True
    assert result["learning_state_a"].exists() is False
    assert result["learning_state_b"].exists() is True
    assert result["learning_a"] == []
    assert result["learning_b"][0]["target_id"] == "release-helper"
    assert result["curator_a"]["paused"] is False
    assert result["curator_b"]["paused"] is True
