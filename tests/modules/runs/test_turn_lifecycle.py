import asyncio
from types import SimpleNamespace

from opensprite.core.contracts.run_events import INBOUND_MEDIA_EVENT_PREFIX, INBOUND_MEDIA_PERSISTED_EVENT
from opensprite.modules.runs.turn_lifecycle import ActiveTurnRun, RunLifecycleService


def test_record_inbound_media_emits_persisted_and_failed_events():
    emitted: list[tuple[tuple, dict]] = []

    async def emit_run_event(*args, **kwargs):
        emitted.append((args, kwargs))

    service = RunLifecycleService(
        run_trace=object(),
        run_state=object(),
        emit_run_event=emit_run_event,
        clear_delegated_task_updates=lambda _run_id: None,
        clear_workflow_outcomes=lambda _run_id: None,
        format_log_preview=lambda value, **_kwargs: value,
    )
    run = ActiveTurnRun(
        session_id="web:chat-1",
        run_id="run-1",
        channel="web",
        external_chat_id="chat-1",
    )
    turn = SimpleNamespace(
        media_events=[
            {"status": "persisted", "path": "image.png"},
            {"status": "failed", "error": "disk full"},
        ]
    )

    asyncio.run(service.record_inbound_media(run=run, turn=turn))

    assert [args[2] for args, _kwargs in emitted] == [
        INBOUND_MEDIA_PERSISTED_EVENT,
        f"{INBOUND_MEDIA_EVENT_PREFIX}failed",
    ]
    assert emitted[0][0][3] == {"schema_version": 1, "status": "persisted", "path": "image.png"}
    assert emitted[1][0][3] == {"schema_version": 1, "status": "failed", "error": "disk full"}
    assert all(kwargs == {"channel": "web", "external_chat_id": "chat-1"} for _args, kwargs in emitted)
