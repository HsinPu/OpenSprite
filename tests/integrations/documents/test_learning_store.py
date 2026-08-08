import json

import pytest

import opensprite.integrations.documents.learning as learning_module
from opensprite.integrations.workspace.paths import get_session_learning_state_file
from opensprite.integrations.documents.learning import JsonLearningLedgerStore
from opensprite.modules.documents.learning import LearningLedger


def test_constructor_requires_exactly_one_path_source(tmp_path):
    with pytest.raises(ValueError, match="exactly one"):
        JsonLearningLedgerStore()

    with pytest.raises(ValueError, match="exactly one"):
        JsonLearningLedgerStore(
            state_path=tmp_path / "learning.json",
            state_path_for_session=lambda _session_id: tmp_path / "other.json",
        )


def test_round_trip_writes_versioned_state_and_copies_entries(tmp_path):
    state_path = tmp_path / "state" / "learning.json"
    store = JsonLearningLedgerStore(state_path=state_path)
    entries = [{"kind": "skill", "metadata": {"verified": True}}]

    store.save_entries("telegram:room-1", entries)
    entries[0]["kind"] = "changed-after-save"

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert raw == {
        "schema_version": 1,
        "entries": [{"kind": "skill", "metadata": {"verified": True}}],
    }
    assert store.load_entries("telegram:room-1") == [
        {"kind": "skill", "metadata": {"verified": True}}
    ]


def test_session_path_resolver_keeps_session_files_separate(tmp_path):
    store = JsonLearningLedgerStore(
        state_path_for_session=lambda session_id: tmp_path / f"{session_id}.json"
    )

    store.save_entries("one", [{"target_id": "first"}])
    store.save_entries("two", [{"target_id": "second"}])

    assert store.load_entries("one") == [{"target_id": "first"}]
    assert store.load_entries("two") == [{"target_id": "second"}]


def test_load_returns_empty_for_missing_malformed_or_invalid_state(tmp_path, monkeypatch):
    state_path = tmp_path / "learning.json"
    store = JsonLearningLedgerStore(state_path=state_path)
    warnings = []
    monkeypatch.setattr(learning_module.logger, "warning", lambda *args: warnings.append(args))

    assert store.load_entries("session") == []
    assert warnings == []

    state_path.write_text("{not-json", encoding="utf-8")
    assert store.load_entries("session") == []
    assert warnings and warnings[-1][0] == "learning.state.load_failed | path=%s error=%s"

    state_path.write_text("[]", encoding="utf-8")
    assert store.load_entries("session") == []

    state_path.write_text(json.dumps({"entries": "invalid"}), encoding="utf-8")
    assert store.load_entries("session") == []


def test_load_and_save_filter_non_object_entries(tmp_path):
    state_path = tmp_path / "learning.json"
    store = JsonLearningLedgerStore(state_path=state_path)

    store.save_entries("session", ["invalid", {"target_id": "kept"}])  # type: ignore[list-item]
    assert store.load_entries("session") == [{"target_id": "kept"}]

    state_path.write_text(
        json.dumps({"schema_version": 1, "entries": [None, {"target_id": "also-kept"}]}),
        encoding="utf-8",
    )
    assert store.load_entries("session") == [{"target_id": "also-kept"}]


def test_clear_is_idempotent(tmp_path):
    state_path = tmp_path / "learning.json"
    store = JsonLearningLedgerStore(state_path=state_path)
    store.save_entries("session", [{"target_id": "item"}])

    store.clear_session("session")
    store.clear_session("session")

    assert not state_path.exists()


def test_clear_failure_is_logged_without_escaping(tmp_path, monkeypatch):
    state_path = tmp_path / "learning.json"
    store = JsonLearningLedgerStore(state_path=state_path)
    store.save_entries("session", [{"target_id": "item"}])
    warnings = []

    def fail_unlink(_path):
        raise OSError("unlink failed")

    monkeypatch.setattr(type(state_path), "unlink", fail_unlink)
    monkeypatch.setattr(learning_module.logger, "warning", lambda *args: warnings.append(args))

    store.clear_session("session")

    assert state_path.exists()
    assert warnings and warnings[-1][0] == "learning.state.delete_failed | path=%s error=%s"


def test_failed_replace_keeps_previous_state_and_cleans_temp_file(tmp_path, monkeypatch):
    state_path = tmp_path / "learning.json"
    store = JsonLearningLedgerStore(state_path=state_path)
    store.save_entries("session", [{"target_id": "before"}])
    previous_content = state_path.read_bytes()
    warnings = []

    def fail_replace(_source, _destination):
        raise OSError("replace failed")

    monkeypatch.setattr(learning_module.os, "replace", fail_replace)
    monkeypatch.setattr(learning_module.logger, "warning", lambda *args: warnings.append(args))

    store.save_entries("session", [{"target_id": "after"}])

    assert state_path.read_bytes() == previous_content
    assert list(tmp_path.glob(".learning.json.*.tmp")) == []
    assert warnings and warnings[-1][0] == "learning.state.save_failed | path=%s error=%s"


def test_path_resolver_errors_propagate(tmp_path):
    def fail_resolver(_session_id):
        raise RuntimeError("resolver failed")

    store = JsonLearningLedgerStore(state_path_for_session=fail_resolver)

    with pytest.raises(RuntimeError, match="resolver failed"):
        store.load_entries("session")


def test_learning_ledger_persists_per_session_file(tmp_path):
    app_home = tmp_path / "home"
    workspace_root = app_home / "workspace"
    def make_store():
        return JsonLearningLedgerStore(
            state_path_for_session=lambda session_id: get_session_learning_state_file(
                session_id,
                app_home=app_home,
                workspace_root=workspace_root,
            )
        )

    ledger = LearningLedger(store=make_store())

    ledger.record_learning(
        "telegram:room-1",
        kind="skill",
        target_id="pytest-helper",
        summary="Reusable pytest workflow.",
        source_run_id="run-1",
    )

    entries = LearningLedger(store=make_store()).recent_entries(
        "telegram:room-1",
        limit=1,
    )

    assert entries[0]["target_id"] == "pytest-helper"
    assert get_session_learning_state_file(
        "telegram:room-1",
        app_home=app_home,
        workspace_root=workspace_root,
    ).exists()


def test_learning_ledger_persists_update_to_existing_file_entry(tmp_path):
    state_path = tmp_path / "learning.json"
    session_id = "telegram:room-1"
    ledger = LearningLedger(store=JsonLearningLedgerStore(state_path=state_path))
    created = ledger.record_learning(
        session_id,
        kind="skill",
        target_id="pytest-helper",
        summary="Before update.",
        source_run_id="run-1",
        metadata={"phase": "before"},
    )

    updated = ledger.record_learning(
        session_id,
        kind="skill",
        target_id="pytest-helper",
        summary="After update.",
        source_run_id="run-2",
        metadata={"verified": True},
    )

    assert updated["summary"] == "After update."
    [persisted] = LearningLedger(
        store=JsonLearningLedgerStore(state_path=state_path)
    ).recent_entries(session_id, limit=10)
    assert persisted["summary"] == "After update."
    assert persisted["source_run_id"] == "run-2"
    assert persisted["created_at"] == created["created_at"]
    assert persisted["metadata"] == {"phase": "before", "verified": True}


def test_learning_ledger_persists_mark_used_for_existing_file_entry(tmp_path):
    state_path = tmp_path / "learning.json"
    session_id = "telegram:room-1"
    ledger = LearningLedger(store=JsonLearningLedgerStore(state_path=state_path))
    ledger.record_learning(
        session_id,
        kind="skill",
        target_id="pytest-helper",
        summary="Reusable pytest workflow.",
        metadata={"origin": "read_skill"},
    )

    first_marked = ledger.mark_used(
        session_id,
        kind="skill",
        target_id="pytest-helper",
        outcome="failed",
        metadata={"attempt": 1},
    )
    second_marked = ledger.mark_used(
        session_id,
        kind="skill",
        target_id="pytest-helper",
        outcome="success",
        metadata={"verified": True},
    )

    assert first_marked["use_count"] == 1
    assert second_marked["use_count"] == 2
    [persisted] = LearningLedger(
        store=JsonLearningLedgerStore(state_path=state_path)
    ).recent_entries(session_id, limit=10)
    assert persisted["use_count"] == 2
    assert persisted["last_outcome"] == "success"
    assert persisted["last_used_at"] is not None
    assert persisted["metadata"] == {
        "origin": "read_skill",
        "attempt": 1,
        "verified": True,
    }
