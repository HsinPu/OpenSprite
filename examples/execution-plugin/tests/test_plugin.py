"""Flow decisions here; installed-wheel tests additionally use the real Host."""
import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
import pytest
from opensprite_backend.agent.plugin import (
    ContextSnapshot, Message, ModelLimits, RunResult, StepResult, CompletionReason, ModelFinishReason,
)
from opensprite_execution_example.plugin import create_plugin_factory


class Host:
    def __init__(self, cancel=False):
        self.requests = []
        self.result = None
        self.nonce = str(uuid4())
        self.cancel = cancel
        self.run = SimpleNamespace(system_prompt="fixed", model_limits=ModelLimits(32000, 4096))
    async def read_context(self, request):
        current = Message(str(uuid4()), str(uuid4()), str(uuid4()), "user", self.nonce, 1, datetime.now(UTC))
        return ContextSnapshot(str(uuid4()), current, (), None)
    async def infer(self, request):
        self.requests.append(request)
        return StepResult(str(uuid4()), request.label + ":" + self.nonce, ModelFinishReason.FINAL)
    async def checkpoint(self):
        if self.cancel: raise asyncio.CancelledError
    async def finish(self, output):
        self.result = RunResult(output.text, CompletionReason.STOP)
        return self.result


def test_review_uses_previous_outputs_and_finishes_only_final():
    host = Host()
    result = asyncio.run(create_plugin_factory().create().execute(host))
    assert result is host.result and result.text == "final:"+host.nonce
    assert [r.channel for r in host.requests] == ["draft", "draft", "answer"]
    assert host.requests[1].messages[-1].content == "draft:"+host.nonce
    assert host.requests[2].messages[-1].content == "Draft review:\nreview:"+host.nonce
    assert host.requests[2].sources[-1].steps[0].text == "review:"+host.nonce


def test_cancellation_stops_before_review():
    host = Host(cancel=True)
    with pytest.raises(asyncio.CancelledError): asyncio.run(create_plugin_factory().create().execute(host))
    assert len(host.requests) == 1 and host.result is None


def test_fresh_instances_use_v5():
    factory = create_plugin_factory()
    assert factory.api_version == 5 and factory.create() is not factory.create()
