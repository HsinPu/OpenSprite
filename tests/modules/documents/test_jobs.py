from dataclasses import FrozenInstanceError

import pytest

from opensprite.modules.documents.jobs import (
    CuratorJob,
    CuratorMaintenanceServices,
    CuratorRequest,
)


async def _noop(_session_id):
    return None


def test_curator_maintenance_services_define_canonical_job_order():
    services = CuratorMaintenanceServices(
        maybe_consolidate_memory=_noop,
        maybe_update_recent_summary=_noop,
        maybe_update_user_profile=_noop,
        read_memory_snapshot=lambda _session_id: "memory",
        read_recent_summary_snapshot=lambda _session_id: "summary",
        read_user_profile_snapshot=lambda _session_id: "profile",
    )

    jobs = services.jobs()

    assert [job.key for job in jobs] == ["memory", "recent_summary", "user_profile"]
    assert [job.label for job in jobs] == ["memory", "recent summary", "user profile"]


def test_curator_request_defaults_to_an_empty_immutable_request():
    request = CuratorRequest(session_id="session-1")

    assert request.maintenance_job_keys == ()
    assert request.run_skill_review is False
    with pytest.raises(FrozenInstanceError):
        request.run_skill_review = True


def test_curator_job_keeps_snapshot_and_runner_callbacks():
    snapshot_reader = lambda session_id: session_id
    job = CuratorJob("memory", "memory", snapshot_reader, _noop)

    assert job.snapshot_reader("session-1") == "session-1"
    assert job.runner is _noop
