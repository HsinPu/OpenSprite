"""exec lifecycle behavior."""

import asyncio
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from opensprite.app.tools.processes.exec import (
    ExecTool,
    _build_pipe_drain_warning_result,
    _build_timeout_result,
)
from opensprite.core.contracts.tool_results import classify_tool_result_status


def _python_shell_command(code: str) -> str:
    argv = [sys.executable, "-u", "-c", code]
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def test_exec_tool_returns_guidance_for_uvicorn(tmp_path):
    tool = ExecTool(workspace=Path(tmp_path))
    result = asyncio.run(tool.execute(command="uvicorn app:app"))
    payload = json.loads(result)
    status = classify_tool_result_status(result)

    assert payload["ok"] is False
    assert payload["error_type"] == "ToolValidationError"
    assert payload["category"] == "invalid_arguments"
    assert payload["invalid_arguments"] is True
    assert payload["metadata"]["tool_name"] == "exec"
    assert payload["metadata"]["command_policy"] == "foreground_exec"
    assert status.invalid_arguments is True
    assert "long-lived" in status.error.lower() or "server" in status.error.lower()


def test_exec_tool_runs_echo_when_allowed(tmp_path):
    tool = ExecTool(workspace=Path(tmp_path))
    result = asyncio.run(tool.execute(command="echo opensprite_exec_ok"))
    assert "opensprite_exec_ok" in result
    assert not result.startswith("Error:")


def test_exec_tool_returns_structured_error_for_runtime_exception():
    def broken_workspace():
        raise RuntimeError("workspace unavailable")

    tool = ExecTool(workspace_resolver=broken_workspace)
    result = asyncio.run(tool.execute(command="echo should_not_run"))
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["error"] == "workspace unavailable"
    assert payload["error_type"] == "ToolExecutionError"
    assert payload["metadata"]["tool_name"] == "exec"


def test_exec_tool_blocks_dangerous_command(tmp_path):
    tool = ExecTool(workspace=Path(tmp_path))
    result = asyncio.run(tool.execute(command="git reset --hard"))
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ToolGuardrailError"
    assert status.category == "blocked_by_policy"
    assert "Command blocked by safety guard:" in status.error
    assert "git reset --hard" in status.error


def test_exec_tool_blocks_wrapped_destructive_command(tmp_path):
    tool = ExecTool(workspace=Path(tmp_path))
    result = asyncio.run(tool.execute(command='powershell -Command "Remove-Item -Recurse ."'))
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ToolGuardrailError"
    assert status.category == "blocked_by_policy"
    assert "powershell -Command" in status.error
    assert "remove-item recursive/forced delete" in status.error


def test_exec_tool_allows_help_for_dangerous_command_names(tmp_path):
    tool = ExecTool(workspace=Path(tmp_path))
    result = asyncio.run(tool.execute(command="Remove-Item --help"))

    assert classify_tool_result_status(result).error_type != "ToolGuardrailError"


def test_exec_tool_accepts_notify_on_exit(tmp_path):
    tool = ExecTool(workspace=Path(tmp_path))

    async def run():
        result = await tool.execute(
            command=_python_shell_command("print('done', flush=True)"),
            background=True,
            notify_on_exit=False,
        )
        sessions = await tool.process_manager.list_sessions()
        return result, sessions

    result, sessions = asyncio.run(run())

    assert "Background session started." in result
    assert len(sessions) == 1
    assert sessions[0].notify_on_exit is False


def test_exec_tool_persists_background_session_lifecycle(tmp_path):
    from opensprite.integrations.persistence.sqlite.storage import SQLiteStorage
    from opensprite.integrations.processes.background_runtime import BackgroundProcessManager
    storage = SQLiteStorage(Path(tmp_path) / "sessions.db")
    manager = BackgroundProcessManager(storage=storage)
    tool = ExecTool(
        workspace=Path(tmp_path),
        process_manager=manager,
        background_session_owner_factory=lambda: {
            "session_id": "chat-1",
            "run_id": "run-1",
            "channel": "web",
            "external_chat_id": "external-1",
        },
    )

    async def run():
        await storage.create_run("chat-1", "run-1", status="running", created_at=1.0)
        result = await tool.execute(
            command=_python_shell_command("print('persisted background', flush=True)"),
            background=True,
            notify_on_exit=False,
        )
        sessions = await manager.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        deadline = time.time() + 5
        while session.state != "exited" and time.time() < deadline:
            await asyncio.sleep(0.05)
            session = (await manager.list_sessions())[0]
        stored = await storage.get_background_process(session.session_id)
        events = await storage.get_run_events("chat-1", "run-1")
        deadline = time.time() + 5
        while len(events) < 2 and time.time() < deadline:
            await asyncio.sleep(0.05)
            events = await storage.get_run_events("chat-1", "run-1")
        return result, session, stored, events

    result, session, stored, events = asyncio.run(run())

    assert "Background session started." in result
    assert session.state == "exited"
    assert stored is not None
    assert stored.owner_session_id == "chat-1"
    assert stored.owner_run_id == "run-1"
    assert stored.state == "exited"
    assert stored.exit_code == 0
    assert stored.notify_mode == "none"
    assert "persisted background" in stored.output_tail
    assert stored.output_path is not None
    assert "persisted background" in Path(stored.output_path).read_text(
        encoding="utf-8"
    )
    assert [event.event_type for event in events] == [
        "background_process.started",
        "background_process.completed",
    ]
    assert events[-1].payload["process_session_id"] == session.session_id
    assert events[-1].payload["exit_code"] == 0


def test_background_process_manager_marks_persisted_running_sessions_lost(tmp_path):
    from opensprite.core.contracts.persistence import StoredBackgroundProcess
    from opensprite.integrations.persistence.sqlite.storage import SQLiteStorage
    from opensprite.integrations.processes.background_runtime import BackgroundProcessManager

    storage = SQLiteStorage(Path(tmp_path) / "sessions.db")
    manager = BackgroundProcessManager(storage=storage)

    async def run():
        await storage.create_run("chat-1", "run-1", status="running", created_at=1.0)
        await storage.upsert_background_process(
            StoredBackgroundProcess(
                process_session_id="proc-running",
                owner_session_id="chat-1",
                owner_run_id="run-1",
                command="npm run dev",
                state="running",
                pid=1234,
                output_tail="server started",
                metadata={"source": "test"},
                started_at=10.0,
                updated_at=11.0,
            )
        )
        await storage.upsert_background_process(
            StoredBackgroundProcess(
                process_session_id="proc-exited",
                owner_session_id="chat-1",
                command="python -m pytest",
                state="exited",
                started_at=12.0,
                updated_at=13.0,
                finished_at=14.0,
            )
        )
        marked = await manager.mark_lost_persisted_sessions()
        lost = await storage.get_background_process("proc-running")
        exited = await storage.get_background_process("proc-exited")
        events = await storage.get_run_events("chat-1", "run-1")
        return marked, lost, exited, events

    marked, lost, exited, events = asyncio.run(run())

    assert marked == 1
    assert lost is not None
    assert lost.state == "lost"
    assert lost.termination_reason == "runtime_restart"
    assert lost.finished_at is not None
    assert lost.output_tail == "server started"
    assert lost.metadata == {
        "source": "test",
        "recovery_reason": "runtime_restart",
        "reattach_supported": False,
        "reattach_reason": "stdout_stderr_and_watch_state_are_runtime_local",
        "lost_policy": "mark_running_processes_lost_on_startup",
    }
    assert exited is not None
    assert exited.state == "exited"
    assert [event.event_type for event in events] == ["background_process.lost"]
    assert events[0].payload["process_session_id"] == "proc-running"
    assert events[0].payload["metadata"]["reattach_supported"] is False


def test_exec_tool_preserves_stdout_stderr_order(tmp_path):
    tool = ExecTool(workspace=Path(tmp_path))
    command = _python_shell_command(
        "import sys, time; "
        "print('out1', flush=True); "
        "time.sleep(0.1); "
        "print('err1', file=sys.stderr, flush=True); "
        "time.sleep(0.1); "
        "print('out2', flush=True)"
    )

    result = asyncio.run(tool.execute(command=command))

    assert "out1" in result
    assert "[stderr] err1" in result
    assert "out2" in result
    assert result.index("out1") < result.index("[stderr] err1") < result.index("out2")


def test_exec_timeout_terminates_descendant_processes(tmp_path):
    marker = Path(tmp_path) / "child-survived.txt"
    child_code = (
        "import pathlib, time; "
        "time.sleep(2); "
        f"pathlib.Path({str(marker)!r}).write_text('child survived', encoding='utf-8')"
    )
    parent_code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-u', '-c', {child_code!r}]); "
        "print('parent started', flush=True); "
        "time.sleep(10)"
    )

    tool = ExecTool(workspace=Path(tmp_path), timeout=1)
    result = asyncio.run(tool.execute(command=_python_shell_command(parent_code)))
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ToolExecutionError"
    assert status.category == "timeout"
    assert "Command timed out after 1s." in status.error
    assert "parent started" in status.error

    deadline = time.time() + 3
    while time.time() < deadline:
        if marker.exists():
            break
        time.sleep(0.1)

    assert not marker.exists()


def test_exec_parent_exit_terminates_descendant_that_keeps_pipes_open(tmp_path):
    marker = Path(tmp_path) / "orphan-survived.txt"
    child_code = (
        "import pathlib, time; "
        "time.sleep(1); "
        f"pathlib.Path({str(marker)!r}).write_text('child survived', encoding='utf-8')"
    )
    parent_code = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-u', '-c', {child_code!r}], "
        "stdin=subprocess.DEVNULL); "
        "print('parent exited', flush=True)"
    )

    tool = ExecTool(workspace=Path(tmp_path), timeout=3)
    tool._output_drain_timeout = lambda timeout_seconds: 0.2
    result = asyncio.run(tool.execute(command=_python_shell_command(parent_code)))

    assert "parent exited" in result
    assert "output pipes did not close" not in result
    time.sleep(1.2)
    assert not marker.exists()


def test_exec_warns_when_output_readers_linger_after_process_exit(tmp_path, monkeypatch):
    import opensprite.app.tools.processes.exec as shell_module

    class _FinishedProcess:
        pid = 123
        returncode = 0

        async def wait(self):
            return 0

    async def fake_start_shell_process(command, *, cwd, output_chunks):
        output_chunks.extend(
            [
                shell_module.CapturedOutputChunk("stdout", b"parent exiting\n"),
                shell_module.CapturedOutputChunk("stdout", b"child still attached\n"),
            ]
        )

        async def sleeper():
            await asyncio.sleep(1)

        return _FinishedProcess(), [asyncio.create_task(sleeper())]

    monkeypatch.setattr(shell_module, "start_shell_process", fake_start_shell_process)
    terminated = []

    async def fake_terminate_process_tree(process, *, wait_timeout=5):
        terminated.append(process.pid)

    monkeypatch.setattr(shell_module, "terminate_process_tree", fake_terminate_process_tree)

    tool = shell_module.ExecTool(workspace=Path(tmp_path), timeout=1)
    tool._output_drain_timeout = lambda timeout_seconds: 0.1
    result = asyncio.run(tool.execute(command="echo simulated"))

    assert "parent exiting" in result
    assert "child still attached" in result
    assert "output pipes did not close within 0.1s after the shell exited" in result
    assert terminated == [123]


def test_build_timeout_result_appends_pipe_warning_when_not_drained():
    result = _build_timeout_result(3, "partial output", drained=False)
    status = classify_tool_result_status(result)

    assert status.ok is False
    assert status.error_type == "ToolExecutionError"
    assert status.category == "timeout"
    assert "Command timed out after 3s." in status.error
    assert "Partial output before timeout:\npartial output" in status.error
    assert "output pipes did not close promptly after timeout" in status.error


def test_build_pipe_drain_warning_result_mentions_timeout_window():
    result = _build_pipe_drain_warning_result("hello", drain_timeout=7)

    assert result.startswith("hello\n\n")
    assert "output pipes did not close within 7s after the shell exited" in result
