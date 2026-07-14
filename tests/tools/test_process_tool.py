import asyncio
import os
import shlex
import subprocess
import sys
from pathlib import Path

from opensprite.storage import MemoryStorage
from opensprite.tools.process import ProcessTool
from opensprite.tools.process_runtime import BackgroundProcessManager
from opensprite.tools.result_status import classify_tool_result_status
import opensprite.tools.shell as shell_module
from opensprite.tools.shell import ExecTool


def _python_shell_command(code: str) -> str:
    argv = [sys.executable, "-u", "-c", code]
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def _extract_session_id(result: str) -> str:
    for line in result.splitlines():
        if line.startswith("Session ID: "):
            return line.removeprefix("Session ID: ").strip()
    raise AssertionError(f"Session ID missing from result: {result}")


async def _wait_for_session_exit(
    manager: BackgroundProcessManager,
    session_id: str,
    *,
    timeout: float = 3.0,
):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        session = await manager.get_session(session_id)
        if session is not None and session.state == "exited":
            return session
        await asyncio.sleep(0.02)
    raise AssertionError(f"background session did not exit within {timeout}s: {session_id}")


def test_process_poll_missing_session_returns_structured_error():
    async def run() -> None:
        process_tool = ProcessTool(BackgroundProcessManager())

        result = await process_tool.execute(action="poll", session_id="missing-session")
        status = classify_tool_result_status(result)

        assert status.ok is False
        assert status.error_type == "ProcessToolError"
        assert status.category == "process_session_not_found"
        assert "missing-session" in status.error

    asyncio.run(run())


def test_exec_background_starts_managed_session_and_process_tool_can_kill(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=5)
        process_tool = ProcessTool(manager)

        command = _python_shell_command(
            "import time; print('background hello', flush=True); time.sleep(5)"
        )
        started = await exec_tool.execute(
            command=command,
            background=True,
            timeout_seconds=5,
        )

        session_id = _extract_session_id(started)
        assert "Background session started." in started

        listed = await process_tool.execute(action="list")
        assert session_id in listed
        assert "running" in listed
        assert "runtime=" in listed

        await asyncio.sleep(0.2)
        polled = await process_tool.execute(action="poll", session_id=session_id)
        assert "Started: " in polled
        assert "Runtime: " in polled
        assert "background hello" in polled

        killed = await process_tool.execute(action="kill", session_id=session_id)
        assert f"Session ID: {session_id}" in killed
        assert "Finished: " in killed
        assert "Runtime: " in killed
        assert "Termination: killed" in killed

    asyncio.run(run())


def test_background_session_without_explicit_timeout_keeps_running_after_exec_timeout(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=1)
        exec_tool._output_drain_timeout = lambda timeout_seconds: 0.1
        process_tool = ProcessTool(manager)

        started = await exec_tool.execute(
            command=_python_shell_command(
                "import time; print('still alive', flush=True); time.sleep(3)"
            ),
            background=True,
        )
        session_id = _extract_session_id(started)

        await asyncio.sleep(1.3)
        inspected = await process_tool.execute(action="inspect", session_id=session_id)

        assert "Status: running" in inspected
        assert "Termination: timeout" not in inspected

        await process_tool.execute(action="kill", session_id=session_id)

    asyncio.run(run())


def test_background_session_explicit_timeout_still_terminates(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=5)
        exec_tool._output_drain_timeout = lambda timeout_seconds: 0.1
        process_tool = ProcessTool(manager)

        started = await exec_tool.execute(
            command=_python_shell_command(
                "import time; print('timed background', flush=True); time.sleep(2)"
            ),
            background=True,
            timeout_seconds=1,
        )
        session_id = _extract_session_id(started)

        inspected = ""
        for _ in range(20):
            inspected = await process_tool.execute(action="inspect", session_id=session_id)
            if "Status: exited" in inspected:
                break
            await asyncio.sleep(0.2)

        assert "Status: exited" in inspected
        assert "Termination: timeout" in inspected

    asyncio.run(run())


def test_exec_yield_ms_moves_running_command_to_background(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=5)
        process_tool = ProcessTool(manager)

        command = _python_shell_command(
            "import time; print('yielded output', flush=True); time.sleep(1)"
        )
        started = await exec_tool.execute(
            command=command,
            yield_ms=50,
            timeout_seconds=5,
        )

        session_id = _extract_session_id(started)
        assert "moved to background" in started

        await asyncio.sleep(0.2)
        polled = await process_tool.execute(action="poll", session_id=session_id)
        assert "yielded output" in polled

        await process_tool.execute(action="kill", session_id=session_id)

    asyncio.run(run())


def test_process_inspect_returns_metadata_without_output_sections(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=5)
        process_tool = ProcessTool(manager)

        started = await exec_tool.execute(
            command=_python_shell_command("print('inspect me', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        session_id = _extract_session_id(started)
        await _wait_for_session_exit(manager, session_id)

        inspected = await process_tool.execute(action="inspect", session_id=session_id)

        assert f"Session ID: {session_id}" in inspected
        assert "Started: " in inspected
        assert "Runtime: " in inspected
        assert "Has output: yes" in inspected
        assert "Output drained: yes" in inspected
        assert "Termination: exit" in inspected
        assert "Full output:" not in inspected
        assert "New output:" not in inspected
        assert "Output tail:" not in inspected

    asyncio.run(run())


def test_process_tool_shows_run_ownership_metadata(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_session_owner_factory=lambda: {
                "session_id": "web:browser-1",
                "run_id": "run-123",
                "channel": "web",
                "external_chat_id": "browser-1",
            },
        )
        process_tool = ProcessTool(manager)

        started = await exec_tool.execute(
            command=_python_shell_command("print('owned output', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        session_id = _extract_session_id(started)
        await _wait_for_session_exit(manager, session_id)

        listed = await process_tool.execute(action="list")
        inspected = await process_tool.execute(action="inspect", session_id=session_id)

        assert "owner=web:browser-1 / run-123" in listed
        assert "Owner session chat: web:browser-1" in inspected
        assert "Owner run: run-123" in inspected
        assert "Owner channel: web" in inspected
        assert "Owner transport chat: browser-1" in inspected

    asyncio.run(run())


def test_process_log_and_clear_handle_exited_session(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=5)
        process_tool = ProcessTool(manager)

        command = _python_shell_command(
            "print('finished output', flush=True)"
        )
        started = await exec_tool.execute(
            command=command,
            background=True,
            timeout_seconds=5,
        )

        session_id = _extract_session_id(started)
        await _wait_for_session_exit(manager, session_id)

        logged = await process_tool.execute(action="log", session_id=session_id)
        assert "Started: " in logged
        assert "Finished: " in logged
        assert "Runtime: " in logged
        assert "Termination: exit" in logged
        assert "finished output" in logged

        cleared = await process_tool.execute(action="clear", session_id=session_id)
        assert f"Cleared background session '{session_id}'" in cleared

        listed = await process_tool.execute(action="list")
        assert listed == "No background sessions."

    asyncio.run(run())


def test_background_session_exit_notifier_runs_on_natural_completion(tmp_path):
    async def run() -> None:
        notifications = []
        manager = BackgroundProcessManager()

        async def notify(session):
            notifications.append(
                (
                    session.session_id,
                    session.termination_reason,
                    manager.render_output(session, max_chars=None),
                )
            )

        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_notification_factory=lambda: notify,
        )

        started = await exec_tool.execute(
            command=_python_shell_command("print('notify done', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        session_id = _extract_session_id(started)
        await _wait_for_session_exit(manager, session_id)

        assert notifications == [(session_id, "exit", "notify done")]

    asyncio.run(run())


def test_background_session_exit_notifier_records_sent_event(tmp_path):
    async def run() -> list[str]:
        storage = MemoryStorage()
        await storage.create_run("chat-1", "run-1", status="running")
        manager = BackgroundProcessManager(storage=storage)

        async def notify(_session):
            return None

        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_notification_factory=lambda: notify,
            background_session_owner_factory=lambda: {
                "session_id": "chat-1",
                "run_id": "run-1",
            },
        )

        await exec_tool.execute(
            command=_python_shell_command("print('notify done', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        deadline = asyncio.get_running_loop().time() + 5
        events = await storage.get_run_events("chat-1", "run-1")
        while len(events) < 3 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
            events = await storage.get_run_events("chat-1", "run-1")
        return [event.event_type for event in events]

    assert asyncio.run(run()) == [
        "background_process.started",
        "background_process.completed",
        "background_process.notification_sent",
    ]


def test_background_session_exit_notifier_records_failed_event(tmp_path):
    async def run() -> tuple[list[str], dict]:
        storage = MemoryStorage()
        await storage.create_run("chat-1", "run-1", status="running")
        manager = BackgroundProcessManager(storage=storage)

        async def notify(_session):
            raise RuntimeError("notify boom")

        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_notification_factory=lambda: notify,
            background_session_owner_factory=lambda: {
                "session_id": "chat-1",
                "run_id": "run-1",
            },
        )

        await exec_tool.execute(
            command=_python_shell_command("print('notify done', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        deadline = asyncio.get_running_loop().time() + 5
        events = await storage.get_run_events("chat-1", "run-1")
        while len(events) < 3 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
            events = await storage.get_run_events("chat-1", "run-1")
        return [event.event_type for event in events], events[-1].payload

    event_types, payload = asyncio.run(run())

    assert event_types == [
        "background_process.started",
        "background_process.completed",
        "background_process.notification_failed",
    ]
    assert payload["status"] == "failed"
    assert payload["process_session_id"]


def test_background_session_quiet_success_does_not_notify_by_default(tmp_path):
    async def run() -> None:
        notifications = []
        manager = BackgroundProcessManager()

        async def notify(session):
            notifications.append(session.session_id)

        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_notification_factory=lambda: notify,
        )

        started = await exec_tool.execute(
            command=_python_shell_command("pass"),
            background=True,
            timeout_seconds=5,
        )
        await _wait_for_session_exit(manager, _extract_session_id(started))

        assert notifications == []

    asyncio.run(run())


def test_background_session_quiet_success_can_notify_when_enabled(tmp_path):
    async def run() -> None:
        notifications = []
        manager = BackgroundProcessManager()

        async def notify(session):
            notifications.append((session.session_id, session.termination_reason, session.exit_code))

        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_notification_factory=lambda: notify,
        )

        started = await exec_tool.execute(
            command=_python_shell_command("pass"),
            background=True,
            timeout_seconds=5,
            notify_on_exit_empty_success=True,
        )
        session_id = _extract_session_id(started)
        await _wait_for_session_exit(manager, session_id)

        assert notifications == [(session_id, "exit", 0)]

    asyncio.run(run())


def test_background_session_non_success_notifies_even_without_output(tmp_path):
    async def run() -> None:
        notifications = []
        manager = BackgroundProcessManager()

        async def notify(session):
            notifications.append((session.termination_reason, session.exit_code))

        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_notification_factory=lambda: notify,
        )

        started = await exec_tool.execute(
            command=_python_shell_command("import sys; sys.exit(2)"),
            background=True,
            timeout_seconds=5,
        )
        await _wait_for_session_exit(manager, _extract_session_id(started))

        assert notifications == [("exit", 2)]

    asyncio.run(run())


def test_background_session_exit_notifier_is_suppressed_for_manual_kill(tmp_path):
    async def run() -> None:
        notifications = []
        manager = BackgroundProcessManager()

        async def notify(session):
            notifications.append(session.session_id)

        exec_tool = ExecTool(
            workspace=Path(tmp_path),
            process_manager=manager,
            timeout=5,
            background_notification_factory=lambda: notify,
        )
        process_tool = ProcessTool(manager)

        started = await exec_tool.execute(
            command=_python_shell_command("import time; print('kill me', flush=True); time.sleep(5)"),
            background=True,
            timeout_seconds=5,
        )
        session_id = _extract_session_id(started)

        await process_tool.execute(action="kill", session_id=session_id)
        await asyncio.sleep(0.2)

        assert notifications == []

    asyncio.run(run())


def test_process_clear_without_session_id_removes_only_exited_sessions(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager()
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=5)
        process_tool = ProcessTool(manager)

        finished = await exec_tool.execute(
            command=_python_shell_command("print('done', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        running = await exec_tool.execute(
            command=_python_shell_command("import time; print('still running', flush=True); time.sleep(5)"),
            background=True,
            timeout_seconds=5,
        )

        finished_id = _extract_session_id(finished)
        running_id = _extract_session_id(running)
        await _wait_for_session_exit(manager, finished_id)

        cleared = await process_tool.execute(action="clear")
        assert cleared == "Cleared 1 exited background session(s)."

        listed = await process_tool.execute(action="list")
        assert finished_id not in listed
        assert running_id in listed

        await process_tool.execute(action="kill", session_id=running_id)

    asyncio.run(run())


def test_background_manager_prunes_old_exited_sessions(tmp_path):
    async def run() -> None:
        manager = BackgroundProcessManager(max_exited_sessions=1)
        exec_tool = ExecTool(workspace=Path(tmp_path), process_manager=manager, timeout=5)

        first = await exec_tool.execute(
            command=_python_shell_command("print('first', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        first_id = _extract_session_id(first)
        await _wait_for_session_exit(manager, first_id)

        second = await exec_tool.execute(
            command=_python_shell_command("print('second', flush=True)"),
            background=True,
            timeout_seconds=5,
        )
        second_id = _extract_session_id(second)
        await _wait_for_session_exit(manager, second_id)

        sessions = await manager.list_sessions()
        session_ids = [session.session_id for session in sessions]

        assert first_id not in session_ids
        assert second_id in session_ids
        assert len(session_ids) == 1

    asyncio.run(run())


def test_exec_cancellation_terminates_foreground_process(tmp_path, monkeypatch):
    async def run() -> None:
        real_terminate = shell_module.terminate_process_tree
        terminated_pids = []

        async def recording_terminate(process, *, wait_timeout=5):
            terminated_pids.append(process.pid)
            await real_terminate(process, wait_timeout=wait_timeout)

        monkeypatch.setattr(shell_module, "terminate_process_tree", recording_terminate)
        tool = ExecTool(workspace=Path(tmp_path), timeout=30)
        command = _python_shell_command("import time; time.sleep(30)")
        task = asyncio.create_task(tool.execute(command=command, timeout_seconds=30))
        await asyncio.sleep(0.2)

        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=5)
        except asyncio.CancelledError:
            pass

        assert terminated_pids

    asyncio.run(run())


def test_repeated_exec_cancellation_keeps_process_cleanup_running(tmp_path, monkeypatch):
    async def run() -> None:
        process_waiting = asyncio.Event()
        process_exited = asyncio.Event()
        cleanup_entered = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_finished = asyncio.Event()

        class FakeProcess:
            pid = 777
            returncode = None

            async def wait(self):
                process_waiting.set()
                await process_exited.wait()
                return self.returncode

        process = FakeProcess()

        async def fake_start_shell_process(command, *, cwd, output_chunks):
            return process, []

        async def blocking_terminate(process_to_stop, *, wait_timeout=5):
            assert process_to_stop is process
            cleanup_entered.set()
            await cleanup_release.wait()
            process.returncode = -9
            process_exited.set()
            cleanup_finished.set()

        monkeypatch.setattr(shell_module, "start_shell_process", fake_start_shell_process)
        monkeypatch.setattr(shell_module, "terminate_process_tree", blocking_terminate)

        tool = ExecTool(workspace=Path(tmp_path), timeout=30)
        task = asyncio.create_task(tool.execute(command="echo simulated", timeout_seconds=30))
        await asyncio.wait_for(process_waiting.wait(), timeout=1)

        task.cancel()
        await asyncio.wait_for(cleanup_entered.wait(), timeout=1)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=1)
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("CancelledError was not raised")

        assert cleanup_finished.is_set() is False
        cleanup_release.set()
        await asyncio.wait_for(cleanup_finished.wait(), timeout=1)

    asyncio.run(run())


def test_long_lived_commands_are_allowed_when_exec_background_is_requested(tmp_path):
    manager = BackgroundProcessManager()
    tool = ExecTool(workspace=Path(tmp_path), process_manager=manager)

    assert tool._validate_command("uvicorn app:app", allow_managed_background=True) is None
    assert tool._validate_command("sleep 1 &", allow_managed_background=True) is not None
