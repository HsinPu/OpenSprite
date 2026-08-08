import asyncio

from opensprite.app.agent.execution_support.run_hooks import (
    RunHookService,
    tool_warrants_progress_notice,
)
from opensprite.core.contracts.run_events import RUN_PART_DELTA_EVENT


def test_llm_delta_hook_emits_empty_completion_marker():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_llm_delta_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("assistant:run-1:1", "", "running", 1)
        await hook("assistant:run-1:1", "", "completed", 2)

    asyncio.run(scenario())

    assert len(calls) == 1
    assert calls[0][0] == "web:browser-1"
    assert calls[0][1] == "run-1"
    assert calls[0][2] == RUN_PART_DELTA_EVENT
    assert calls[0][3] == {
        "part_id": "assistant:run-1:1",
        "part_type": "assistant_message",
        "content_delta": "",
        "state": "completed",
        "sequence": 2,
    }
    assert calls[0][4] == {"channel": "web", "external_chat_id": "browser-1"}


def test_llm_status_hook_uses_structured_status_only():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_llm_status_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("The article says retry policies are useful.")
        await hook({"message": "Retrying provider request.", "status": "retry", "trigger": "provider_retry"})

    asyncio.run(scenario())

    assert calls == [
        (
            "web:browser-1",
            "run-1",
            "llm_status",
            {"message": "The article says retry policies are useful."},
            {"channel": "web", "external_chat_id": "browser-1"},
        ),
        (
            "web:browser-1",
            "run-1",
            "llm_status",
            {"status": "retry", "trigger": "provider_retry", "message": "Retrying provider request."},
            {"channel": "web", "external_chat_id": "browser-1"},
        ),
    ]


def test_tool_input_delta_hook_emits_tool_input_events():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_tool_input_delta_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("call-1", "demo", '{"value"', 1)

    asyncio.run(scenario())

    assert calls == [
        (
            "web:browser-1",
            "run-1",
            "tool_input_delta",
            {"tool_call_id": "call-1", "tool_name": "demo", "input_delta": '{"value"', "sequence": 1},
            {"channel": "web", "external_chat_id": "browser-1"},
        )
    ]


def test_reasoning_delta_hook_emits_inspector_only_events():
    calls = []

    async def emit_run_event(session_id, run_id, event_type, payload, **kwargs):
        calls.append((session_id, run_id, event_type, payload, kwargs))

    service = RunHookService(
        message_bus_getter=lambda: None,
        add_run_part=lambda *args, **kwargs: None,
        emit_run_event=emit_run_event,
        format_log_preview=lambda text, max_chars=200: str(text)[:max_chars],
    )
    hook = service.make_reasoning_delta_hook(
        channel="web",
        external_chat_id="browser-1",
        session_id="web:browser-1",
        run_id="run-1",
        enabled=True,
    )

    async def scenario():
        await hook("thinking", 1)

    asyncio.run(scenario())

    assert calls == [
        (
            "web:browser-1",
            "run-1",
            "reasoning_delta",
            {"content_delta": "thinking", "sequence": 1, "inspector_only": True},
            {"channel": "web", "external_chat_id": "browser-1"},
        )
    ]


def test_progress_notice_policy_includes_long_running_tool_types():
    assert tool_warrants_progress_notice("read_skill") is True
    assert tool_warrants_progress_notice("delegate") is True
    assert tool_warrants_progress_notice("delegate_many") is True
    assert tool_warrants_progress_notice("run_workflow") is True
    assert tool_warrants_progress_notice("mcp_demo_echo") is True
    assert tool_warrants_progress_notice("web_search") is False
