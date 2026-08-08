import asyncio

from agent_test_helpers import make_agent_loop
from opensprite.app.agent.execution import ExecutionResult


def test_skill_review_scheduler_coalesces_same_session_into_rerun(tmp_path):
    async def scenario():
        agent = make_agent_loop(tmp_path)
        agent._skill_review_tool_registry = lambda: object()

        release = asyncio.Event()
        started = asyncio.Event()
        calls: list[str] = []

        async def fake_run(session_id: str) -> None:
            calls.append(session_id)
            started.set()
            if len(calls) == 1:
                await release.wait()

        agent._run_skill_review = fake_run
        result = ExecutionResult(content="done", executed_tool_calls=agent.config.skill_review_min_tool_calls)

        agent._maybe_schedule_skill_review("chat-a", result)
        await started.wait()
        agent._maybe_schedule_skill_review("chat-a", result)

        release.set()
        await agent.wait_for_background_skill_reviews()
        return calls

    calls = asyncio.run(scenario())

    assert calls == ["chat-a", "chat-a"]


def test_skill_review_scheduler_keeps_different_sessions_separate(tmp_path):
    async def scenario():
        agent = make_agent_loop(tmp_path)
        agent._skill_review_tool_registry = lambda: object()

        release = asyncio.Event()
        started = set()
        calls: list[str] = []

        async def fake_run(session_id: str) -> None:
            calls.append(session_id)
            started.add(session_id)
            if len(started) < 2:
                await asyncio.sleep(0)
            await release.wait()

        agent._run_skill_review = fake_run
        result = ExecutionResult(content="done", executed_tool_calls=agent.config.skill_review_min_tool_calls)

        agent._maybe_schedule_skill_review("chat-a", result)
        agent._maybe_schedule_skill_review("chat-b", result)
        await asyncio.sleep(0)
        assert sorted(agent._skill_review_tasks) == ["chat-a", "chat-b"]

        release.set()
        await agent.wait_for_background_skill_reviews()
        return calls

    calls = asyncio.run(scenario())

    assert sorted(calls) == ["chat-a", "chat-b"]
