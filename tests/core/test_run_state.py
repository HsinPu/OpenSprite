import asyncio

from opensprite.core.run_tracking.state import (
    ActiveRunState,
    AgentRunStateService,
    RunBusyError,
    RunCancelledError,
)


def test_run_state_prevents_overlapping_runs_for_same_session():
    service = AgentRunStateService()
    service.start("web:browser-1", "run-1")

    try:
        service.start("web:browser-1", "run-2")
    except RunBusyError as exc:
        assert "run-1" in str(exc)
    else:
        raise AssertionError("RunBusyError was not raised")


def test_run_state_tracks_cancel_request_and_finish():
    service = AgentRunStateService()
    service.start("web:browser-1", "run-1")

    active = service.request_cancel("web:browser-1", "run-1")

    assert active is not None
    assert service.is_cancel_requested("web:browser-1", "run-1") is True
    service.finish("web:browser-1", "run-1")
    assert service.get_active("web:browser-1") is None


def test_start_replaces_same_run_id_with_fresh_mutable_state():
    service = AgentRunStateService()
    first = service.start("web:browser-1", "run-1")
    first.cancel_requested = True

    second = service.start("web:browser-1", "run-1")

    assert second is not first
    assert second.cancel_requested is False
    assert service.get_active("web:browser-1") is second


def test_finish_ignores_a_stale_run_id():
    service = AgentRunStateService()
    active = service.start("web:browser-1", "run-2")

    service.finish("web:browser-1", "run-1")

    assert service.get_active("web:browser-1") is active


def test_cancel_request_is_idempotent_and_mutates_the_active_state():
    service = AgentRunStateService()
    active = service.start("web:browser-1", "run-1")

    first_result = service.request_cancel("web:browser-1", "run-1")
    first_requested_at = active.cancel_requested_at
    second_result = service.request_cancel("web:browser-1", "run-1")

    assert first_result is active
    assert second_result is active
    assert active.cancel_requested is True
    assert active.cancel_requested_at is first_requested_at


def test_run_cancelled_error_remains_an_asyncio_cancellation():
    assert issubclass(RunCancelledError, asyncio.CancelledError)


def test_run_state_types_have_one_canonical_module():
    for run_state_type in (
        ActiveRunState,
        AgentRunStateService,
        RunBusyError,
        RunCancelledError,
    ):
        assert run_state_type.__module__ == "opensprite.core.run_tracking.state"
