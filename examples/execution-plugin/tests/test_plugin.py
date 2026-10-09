"""Unit flow checks; real installed-wheel/core verification is in scripts/."""
import asyncio
from uuid import uuid4
import pytest
from opensprite_backend.agent.plugin import RunResult, StepResult
from opensprite_backend.conversations.models import CompletionReason
from opensprite_backend.inference.models import ModelFinishReason
from opensprite_execution_example.plugin import create_plugin_factory


class Host:
    def __init__(self, cancel=False):
        self.requests = []
        self.result = None
        self.nonce = str(uuid4())
        self.cancel = cancel
    async def context(self): return object()
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
    assert host.requests[1].messages[0].content == "draft:"+host.nonce
    assert host.requests[2].messages[-1].content == "Draft review:\nreview:"+host.nonce


def test_cancellation_stops_before_review():
    host = Host(cancel=True)
    with pytest.raises(asyncio.CancelledError): asyncio.run(create_plugin_factory().create().execute(host))
    assert len(host.requests) == 1 and host.result is None


def test_fresh_instances_use_v4():
    factory = create_plugin_factory()
    assert factory.api_version == 4 and factory.create() is not factory.create()
