from opensprite.modules.documents.curator_state import (
    CURATOR_HISTORY_LIMIT,
    CURATOR_STATE_SCHEMA_VERSION,
    default_curator_state,
    normalize_curator_state,
)


def test_default_curator_state_has_current_schema_and_independent_collections():
    first = default_curator_state()
    second = default_curator_state()

    assert first["schema_version"] == CURATOR_STATE_SCHEMA_VERSION
    assert first["run_count"] == 0
    assert first["paused"] is False
    first["history"].append({"run_id": "run-1"})
    assert second["history"] == []


def test_normalize_curator_state_keeps_expected_fields_and_limits_history():
    payload = {
        "paused": True,
        "run_count": "3",
        "last_run_jobs": ["memory", "", 7],
        "last_run_job_results": [{"key": "memory"}, "bad"],
        "history": [{"run_id": str(index)} for index in range(CURATOR_HISTORY_LIMIT + 2)],
    }

    state = normalize_curator_state(payload)

    assert state["paused"] is True
    assert state["run_count"] == 3
    assert state["last_run_jobs"] == ["memory", "7"]
    assert state["last_run_job_results"] == [{"key": "memory"}]
    assert [item["run_id"] for item in state["history"]] == [str(index) for index in range(2, CURATOR_HISTORY_LIMIT + 2)]


def test_normalize_curator_state_recovers_from_invalid_shapes():
    state = normalize_curator_state(
        {
            "run_count": "not-a-number",
            "last_run_jobs": "memory",
            "last_run_job_results": [None, {"key": "profile"}],
            "history": None,
            "unknown": "discarded",
        }
    )

    assert state["run_count"] == 0
    assert state["last_run_jobs"] == []
    assert state["last_run_job_results"] == [{"key": "profile"}]
    assert state["history"] == []
    assert "unknown" not in state
