import asyncio
from uuid import uuid4

import pytest

from opensprite_backend.agent.request_trace import Attempt, TracedGateway
from opensprite_backend.conversations.attempt_events import valid_attempt_payload
from opensprite_backend.inference.models import ModelRequest, ModelMessage, ModelCompleted, ModelFinishReason, ModelUsage


class Recorder:
    def __init__(self):
        self.events = []

    def append_run_event(self, run_id, event_type, data):
        assert valid_attempt_payload(data)
        self.events.append((run_id, data))


def request():
    return ModelRequest(provider_id="openai", model_id="test", response_mode="default",
                        messages=(ModelMessage(role="user", content="private"),), tools=())


def test_attempt_metadata_rejects_secrets_and_invalid_identity():
    data = Attempt(str(uuid4()), str(uuid4()), "main").payload("started")
    assert valid_attempt_payload(data)
    assert not valid_attempt_payload({**data, "prompt": "private"})
    assert not valid_attempt_payload({**data, "attemptNumber": True})
    assert not valid_attempt_payload({**data, "attemptNumber": 2})
    assert not valid_attempt_payload({**data, "requestId": "wrong"})


def test_scope_isolation_and_late_provider_usage():
    async def run():
        class Gateway:
            async def stream(self, request):
                await asyncio.sleep(0)
                yield ModelCompleted(ModelFinishReason.FINAL)
                yield ModelUsage(12, 3)

        recorder = Recorder()
        gateway = TracedGateway(Gateway(), recorder)
        attempts = [Attempt(str(uuid4()), str(uuid4()), "compaction") for _ in range(2)]

        async def consume(attempt):
            with gateway.scope(attempt):
                return [event async for event in gateway.stream(request())]

        await asyncio.gather(*(consume(attempt) for attempt in attempts))
        for attempt in attempts:
            events = [data for run_id, data in recorder.events if run_id == attempt.run_id]
            assert [data["status"] for data in events] == ["started", "completed"]
            assert all(data["attemptId"] == attempt.id for data in events)
            assert events[-1]["inputTokens"] == 12
            assert events[-1]["outputTokens"] == 3
            assert "private" not in str(events)
        count = len(recorder.events)
        _ = [event async for event in gateway.stream(request())]
        assert len(recorder.events) == count
    asyncio.run(run())


def test_cancellation_has_terminal_event_without_replaying_gateway():
    async def run():
        entered = asyncio.Event()
        class Gateway:
            calls = 0
            async def stream(self, request):
                self.calls += 1
                entered.set()
                await asyncio.Event().wait()
                yield ModelCompleted(ModelFinishReason.FINAL)
        delegate = Gateway()
        recorder = Recorder()
        gateway = TracedGateway(delegate, recorder)
        attempt = Attempt(str(uuid4()), str(uuid4()), "main")
        async def consume():
            return [event async for event in gateway.stream(request(), attempt=attempt)]
        task = asyncio.create_task(consume())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert [data["status"] for _, data in recorder.events] == ["started", "cancelled"]
        assert delegate.calls == 1
    asyncio.run(run())
