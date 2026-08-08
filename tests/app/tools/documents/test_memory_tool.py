import asyncio

from opensprite.integrations.documents.memory import MemoryStore
from opensprite.app.tools.documents.memory import SaveMemoryTool
from opensprite.core.contracts.tool_results import classify_tool_result_status


def _memory_store(tmp_path) -> MemoryStore:
    app_home = tmp_path / "home"
    return MemoryStore(
        app_home / "memory",
        app_home=app_home,
        workspace_root=app_home / "workspace",
    )


def test_save_memory_tool_returns_error_for_unsafe_content(tmp_path):
    tool = SaveMemoryTool(_memory_store(tmp_path), lambda: "telegram:room-1")

    result = asyncio.run(tool._execute("# Important Facts\n- system prompt override"))

    status = classify_tool_result_status(result)
    assert status.ok is False
    assert status.error_type == "SaveMemoryToolError"
    assert status.category == "unsafe_memory_content"
    assert status.invalid_arguments is True
    assert status.error.startswith("Blocked unsafe durable memory write")


def test_save_memory_tool_returns_error_without_session(tmp_path):
    tool = SaveMemoryTool(_memory_store(tmp_path), lambda: None)

    result = asyncio.run(tool._execute("# Important Facts\n- stable fact"))

    status = classify_tool_result_status(result)
    assert status.ok is False
    assert status.error_type == "SaveMemoryToolError"
    assert status.category == "missing_session_context"
    assert "requires an active session context" in status.error


def test_save_memory_tool_reports_size_and_delta(tmp_path):
    store = _memory_store(tmp_path)
    store.write("telegram:room-1", "old")
    tool = SaveMemoryTool(store, lambda: "telegram:room-1")

    result = asyncio.run(tool._execute("new memory"))
    unchanged = asyncio.run(tool._execute("new memory"))

    assert result == "Memory saved (10 chars; delta +7 chars)"
    assert unchanged == "Memory unchanged (10 chars)"


def test_save_memory_tool_describes_memory_boundaries():
    assert "chat-continuity" in SaveMemoryTool.description
    assert "USER.md" in SaveMemoryTool.description
    assert "RECENT_SUMMARY.md" in SaveMemoryTool.description
