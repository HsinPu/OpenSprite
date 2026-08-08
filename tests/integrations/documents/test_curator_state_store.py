import json

from opensprite.integrations.documents.curator_state import CuratorStateStore


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


def test_curator_state_store_keeps_in_memory_sessions_separate():
    store = CuratorStateStore()

    store.save("chat-a", {"run_count": 1})
    store.save("chat-b", {"run_count": 2})

    assert store.load("chat-a")["run_count"] == 1
    assert store.load("chat-b")["run_count"] == 2


def test_curator_state_store_uses_per_session_paths(tmp_path):
    store = CuratorStateStore(state_path_for_session=lambda session_id: tmp_path / f"{session_id}.json")

    store.save("chat-a", {"run_count": 4})

    assert store.state_file_for_session("chat-a") == tmp_path / "chat-a.json"
    assert store.load("chat-a")["run_count"] == 4


def test_curator_state_store_recovers_from_invalid_json(tmp_path):
    state_path = tmp_path / "curator_state.json"
    state_path.write_text("{invalid", encoding="utf-8")

    state = CuratorStateStore(state_path=state_path).load("chat-a")

    assert state["run_count"] == 0
    assert state["history"] == []
