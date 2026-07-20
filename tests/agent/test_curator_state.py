import json

from opensprite.documents.curator_state import (
    CURATOR_HISTORY_LIMIT,
    CURATOR_STATE_SCHEMA_VERSION,
    CuratorStateStore,
    normalize_curator_state,
)


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


def test_curator_state_store_round_trips_file_state(tmp_path):
    state_path = tmp_path / "curator_state.json"
    store = CuratorStateStore(state_path=state_path)

    store.save("chat-a", {"paused": True, "run_count": "2", "last_run_changed": ["memory"]})
    loaded = store.load("chat-a")

    assert loaded["paused"] is True
    assert loaded["run_count"] == 2
    assert loaded["last_run_changed"] == ["memory"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["run_count"] == 2

    store.clear("chat-a")

    assert not state_path.exists()
    assert store.load("chat-a")["run_count"] == 0
