import json

import pytest

from opensprite.integrations.documents.progress_state import JsonProgressStore


def test_constructor_creates_parent_without_creating_state_file(tmp_path):
    state_file = tmp_path / "nested" / "progress.json"

    JsonProgressStore(state_file)

    assert state_file.parent.is_dir()
    assert not state_file.exists()


def test_load_state_handles_missing_malformed_and_non_object_json(tmp_path):
    state_file = tmp_path / "progress.json"
    store = JsonProgressStore(state_file)

    assert store.load_state() == {}

    state_file.write_text("{broken", encoding="utf-8")
    assert store.load_state() == {}

    state_file.write_text("[1, 2]", encoding="utf-8")
    assert store.load_state() == {}


def test_load_state_normalizes_values_and_skips_invalid_entries(tmp_path):
    state_file = tmp_path / "progress.json"
    state_file.write_text(
        json.dumps(
            {
                "string": "3",
                "negative": -4,
                "float": 2.9,
                "boolean": True,
                "none": None,
                "invalid": "bad",
            }
        ),
        encoding="utf-8",
    )

    assert JsonProgressStore(state_file).load_state() == {
        "string": 3,
        "negative": 0,
        "float": 2,
        "boolean": 1,
    }


def test_save_state_normalizes_keys_values_and_format(tmp_path):
    state_file = tmp_path / "progress.json"
    store = JsonProgressStore(state_file)

    store.save_state({"chat-a": -2, "會話": "4"})

    assert state_file.read_text(encoding="utf-8") == '{\n  "chat-a": 0,\n  "會話": 4\n}\n'


def test_save_state_propagates_invalid_values(tmp_path):
    store = JsonProgressStore(tmp_path / "progress.json")

    with pytest.raises(ValueError):
        store.save_state({"chat-a": "bad"})


def test_processed_index_updates_preserve_other_scopes_and_clamp_negative_values(tmp_path):
    state_file = tmp_path / "progress.json"
    store = JsonProgressStore(state_file)

    store.set_processed_index("chat-a", 3)
    store.set_processed_index("chat-b", 8)
    store.set_processed_index("chat-a", -5)

    reloaded = JsonProgressStore(state_file)
    assert reloaded.get_processed_index("chat-a") == 0
    assert reloaded.get_processed_index("chat-b") == 8
    assert reloaded.get_processed_index("missing") == 0
