"""Example control flow; installed-wheel verification is separate."""

import asyncio
from dataclasses import dataclass
from uuid import uuid4

import pytest
from opensprite_backend.agent.plugin import DriverResult, ModelTurn
from opensprite_backend.agent.plugin import CompletionState, ContextRetryState
from opensprite_backend.conversations.models import CompletionReason
from opensprite_backend.inference.models import ModelFinishReason
from opensprite_execution_example.plugin import create_plugin_factory


@dataclass
class ScriptedHost:
    turn: ModelTurn
    cancel_at_checkpoint: int | None = None
    issued_result: DriverResult | None = None
    checkpoints: int = 0
    model_calls: int = 0

    async def checkpoint(self):
        self.checkpoints += 1
        if self.checkpoints == self.cancel_at_checkpoint:
            raise asyncio.CancelledError

    async def next_turn(self):
        self.model_calls += 1
        return self.turn

    async def finish(self, turn):
        assert turn is self.turn
        reason = CompletionReason.STOP if turn.finish_reason is ModelFinishReason.FINAL else CompletionReason.OUTPUT_LIMIT
        self.issued_result = DriverResult(turn.text, reason)
        return self.issued_result


@pytest.mark.parametrize("reason", list(ModelFinishReason))
def test_preserves_host_turn_and_returns_exact_result(reason):
    text = "variable answer " + str(uuid4())
    host = ScriptedHost(ModelTurn(text, reason))
    result = asyncio.run(create_plugin_factory().create().execute(host))
    assert result is host.issued_result and result.text == text
    assert host.model_calls == 1 and host.checkpoints == 2


@pytest.mark.parametrize("checkpoint,model_calls", [(1, 0), (2, 1)])
def test_cancellation_does_not_finish_or_fabricate_output(checkpoint, model_calls):
    host = ScriptedHost(ModelTurn(str(uuid4()), ModelFinishReason.FINAL), cancel_at_checkpoint=checkpoint)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(create_plugin_factory().create().execute(host))
    assert host.model_calls == model_calls and host.issued_result is None


def test_host_failure_propagates_without_fabricated_result():
    class FailingHost(ScriptedHost):
        async def next_turn(self):
            raise RuntimeError("fixture host failure")
    host = FailingHost(ModelTurn("", ModelFinishReason.FINAL))
    with pytest.raises(RuntimeError, match="fixture host failure"):
        asyncio.run(create_plugin_factory().create().execute(host))
    assert host.issued_result is None


def test_factories_create_fresh_api_v3_instances():
    loop = create_plugin_factory()
    assert type(loop.api_version) is int and loop.api_version == 3
    assert loop.create() is not loop.create()


@pytest.mark.parametrize("phase,cause,allowed", [
    ("main", "provider_context_limit", True), ("main", "local_budget", False),
    ("continuation", "provider_context_limit", False), ("continuation", "local_budget", False),
])
def test_retry_only_for_eligible_main_provider_limit(phase, cause, allowed):
    assert create_plugin_factory().create().allow_context_retry(ContextRetryState(phase, cause)) is allowed


@pytest.mark.parametrize("configured", ["off", "2", "unlimited"])
def test_policy_vetoes_output_continuation(configured):
    assert create_plugin_factory().create().allow_output_continuation(
        CompletionState(ModelFinishReason.OUTPUT_LIMIT, configured)) is False
