import pytest

from opensprite.integrations.workspace.paths import (
    get_session_recent_summary_file,
    get_session_recent_summary_state_file,
)
from opensprite.integrations.documents.recent_summary import RecentSummaryStore


def test_recent_summary_store_requires_a_session_path_root(tmp_path):
    memory_dir = tmp_path / "memory"

    with pytest.raises(ValueError, match="requires app_home or workspace_root"):
        RecentSummaryStore(memory_dir)

    assert memory_dir.is_dir()


def test_recent_summary_store_writes_context_and_progress_into_session_tree(tmp_path):
    app_home = tmp_path / "home"
    workspace_root = app_home / "workspace"
    memory_dir = app_home / "memory"
    store = RecentSummaryStore(memory_dir, app_home=app_home, workspace_root=workspace_root)

    session_summary = get_session_recent_summary_file(
        "telegram:room-1",
        app_home=app_home,
        workspace_root=workspace_root,
    )
    session_state = get_session_recent_summary_state_file(
        "telegram:room-1",
        app_home=app_home,
        workspace_root=workspace_root,
    )
    store.write("telegram:room-1", "new summary")
    store.set_processed_index("telegram:room-1", 8)

    assert store.read("telegram:room-1") == "new summary"
    assert store.get_context("telegram:room-1") == "# Recent Summary\n\nnew summary"
    assert session_summary.read_text(encoding="utf-8") == "new summary"
    assert session_state.is_file()
    assert store.get_processed_index("telegram:room-1") == 8


def test_recent_summary_store_keeps_sessions_separate(tmp_path):
    store = RecentSummaryStore(
        tmp_path / "memory",
        app_home=tmp_path / "home",
        workspace_root=tmp_path / "workspace",
    )

    store.write("web:chat-a", "summary a")
    store.write("web:chat-b", "summary b")
    store.set_processed_index("web:chat-a", 3)
    store.set_processed_index("web:chat-b", 7)

    assert store.read("web:chat-a") == "summary a"
    assert store.read("web:chat-b") == "summary b"
    assert store.get_processed_index("web:chat-a") == 3
    assert store.get_processed_index("web:chat-b") == 7


def test_recent_summary_store_clear_removes_summary_and_resets_progress(tmp_path):
    store = RecentSummaryStore(
        tmp_path / "memory",
        app_home=tmp_path / "home",
        workspace_root=tmp_path / "workspace",
    )
    store.write("web:chat-a", "summary")
    store.set_processed_index("web:chat-a", 5)

    store.clear("web:chat-a")

    assert store.read("web:chat-a") == ""
    assert store.get_context("web:chat-a") == ""
    assert store.get_processed_index("web:chat-a") == 0
