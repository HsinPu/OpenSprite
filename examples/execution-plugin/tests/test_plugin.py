"""Behavior of the example only; core authority has separate backend tests."""

import asyncio
from dataclasses import dataclass, field

import pytest

from opensprite_backend.agent.driver import DriverResult, ModelTurn
from opensprite_backend.agent.strategies import CompletionState, ContextRetryState
from opensprite_backend.conversations.models import CompletionReason
from opensprite_backend.inference.models import ModelFinishReason, ModelToolCall
from opensprite_execution_example.plugin import create_loop_factory, create_policy_factory


@dataclass
class ScriptedHost:
    turns: list[ModelTurn]
    cancel_at_checkpoint: int | None = None
    completed_tools: list[ModelTurn] = field(default_factory=list)
    issued_result: DriverResult | None = None
    outstanding: ModelTurn | None = None
    checkpoints: int = 0

    async def checkpoint(self):
        self.checkpoints += 1
        if self.checkpoints == self.cancel_at_checkpoint:
            raise asyncio.CancelledError

    async def next_turn(self):
        assert self.outstanding is None, "a tool turn must be settled first"
        self.outstanding = self.turns.pop(0)
        return self.outstanding

    async def execute_tools(self, turn):
        assert turn is self.outstanding and turn.tool_calls
        self.completed_tools.append(turn)
        self.outstanding = None

    async def finish(self, turn):
        assert turn is self.outstanding and not turn.tool_calls
        self.issued_result = DriverResult(turn.text, CompletionReason.STOP)
        return self.issued_result


def tool_turn(identifier):
    return ModelTurn("", ModelFinishReason.TOOL_CALLS,
                     (ModelToolCall(identifier, "calculator", {"expression": "2 + 3"}),))


def test_tools_are_settled_before_final_and_the_host_result_is_returned_unchanged():
    first, second = tool_turn("first"), tool_turn("second")
    host = ScriptedHost([first, second, ModelTurn("model-owned answer", ModelFinishReason.FINAL)])
    result = asyncio.run(create_loop_factory().create().execute(host))

    assert host.completed_tools == [first, second]
    assert result is host.issued_result
    assert result.text == "model-owned answer"


def test_stop_between_model_and_tool_phase_does_not_execute_the_tool():
    host = ScriptedHost([tool_turn("first")], cancel_at_checkpoint=2)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(create_loop_factory().create().execute(host))
    assert host.completed_tools == []
    assert host.issued_result is None


def test_host_failure_is_propagated_without_a_fabricated_result():
    class FailingHost(ScriptedHost):
        async def execute_tools(self, turn):
            raise RuntimeError("fixture host failure")

    host = FailingHost([tool_turn("first")])
    with pytest.raises(RuntimeError, match="fixture host failure"):
        asyncio.run(create_loop_factory().create().execute(host))
    assert host.issued_result is None


def test_each_factory_call_creates_new_execution_objects():
    loop_factory = create_loop_factory()
    policy_factory = create_policy_factory()
    assert type(loop_factory.api_version) is int and loop_factory.api_version == 1
    assert type(policy_factory.api_version) is int and policy_factory.api_version == 1
    assert loop_factory.create() is not loop_factory.create()
    assert policy_factory.create() is not policy_factory.create()


@pytest.mark.parametrize("phase,cause,allowed", [
    ("main", "provider_context_limit", True),
    ("main", "local_budget", False),
    ("continuation", "provider_context_limit", False),
    ("continuation", "local_budget", False),
])
def test_context_retry_is_limited_to_the_main_provider_limit(phase, cause, allowed):
    decision = create_policy_factory().create().allow_context_retry(ContextRetryState(phase, cause))
    assert type(decision) is bool and decision is allowed


@pytest.mark.parametrize("configured", ["off", "2", "unlimited"])
def test_policy_does_not_enable_continuation_for_any_user_setting(configured):
    decision = create_policy_factory().create().allow_output_continuation(
        CompletionState(ModelFinishReason.OUTPUT_LIMIT, configured))
    assert type(decision) is bool and decision is False
