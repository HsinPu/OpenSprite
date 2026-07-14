import asyncio
import io

import pytest

from opensprite.tools import shell_runtime as shell_runtime_module
from opensprite.tools import _windows_shell_launcher as windows_launcher_module
from opensprite.utils import processes as processes_module


class _FakeProcess:
    def __init__(self, *, pid: int = 123):
        self.pid = pid
        self.stdout = None
        self.stderr = None


class _FakeStdin:
    def __init__(self):
        self.closed = False
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None

    def close(self):
        self.closed = True


class _FakeWindowsProcess(_FakeProcess):
    def __init__(self, *, pid: int = 123, stdin=None):
        super().__init__(pid=pid)
        self.stdin = stdin
        self.returncode = None


def test_start_shell_process_uses_expected_stdio_and_session_kwargs(monkeypatch):
    shell_calls = []

    async def fake_create_subprocess_shell(*args, **kwargs):
        shell_calls.append((args, kwargs))
        return _FakeProcess(pid=321)

    monkeypatch.setattr(processes_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(shell_runtime_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(
        shell_runtime_module.asyncio,
        "create_subprocess_shell",
        fake_create_subprocess_shell,
    )

    async def run():
        output_chunks = []
        process, read_tasks = await shell_runtime_module.start_shell_process(
            "echo hi",
            cwd="/tmp/demo",
            output_chunks=output_chunks,
        )
        drained = await shell_runtime_module.drain_process_output(read_tasks, timeout=0.01)
        return process, drained, output_chunks

    process, drained, output_chunks = asyncio.run(run())

    assert process.pid == 321
    assert drained is True
    assert output_chunks == []
    assert shell_calls == [
        (
            ("echo hi",),
            {
                "stdout": shell_runtime_module.asyncio.subprocess.PIPE,
                "stderr": shell_runtime_module.asyncio.subprocess.PIPE,
                "stdin": shell_runtime_module.asyncio.subprocess.DEVNULL,
                "cwd": "/tmp/demo",
                "start_new_session": True,
            },
        )
    ]


def test_windows_shell_start_fails_closed_when_job_attach_fails(monkeypatch):
    process = _FakeWindowsProcess(pid=654, stdin=_FakeStdin())
    terminated = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    async def fake_terminate_process_tree(process_to_stop, *, wait_timeout):
        terminated.append((process_to_stop, wait_timeout))

    monkeypatch.setattr(shell_runtime_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        shell_runtime_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(shell_runtime_module, "attach_process_tree", lambda candidate: False)
    monkeypatch.setattr(
        shell_runtime_module,
        "terminate_process_tree",
        fake_terminate_process_tree,
    )

    async def run():
        with pytest.raises(RuntimeError, match="attach Windows command launcher"):
            await shell_runtime_module.start_shell_process(
                "echo should-not-run",
                cwd=None,
                output_chunks=[],
            )

    asyncio.run(run())

    assert process.stdin.writes == []
    assert process.stdin.closed is True
    assert terminated == [(process, shell_runtime_module._STARTUP_CLEANUP_WAIT_SECONDS)]


def test_windows_shell_start_cancellation_cleans_up_spawned_launcher(monkeypatch):
    async def run() -> None:
        drain_started = asyncio.Event()
        drain_blocker = asyncio.Event()
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_finished = asyncio.Event()
        terminated = []

        class _BlockingStdin(_FakeStdin):
            async def drain(self):
                drain_started.set()
                await drain_blocker.wait()

        process = _FakeWindowsProcess(pid=987, stdin=_BlockingStdin())

        async def fake_create_subprocess_exec(*args, **kwargs):
            return process

        async def fake_terminate_process_tree(process_to_stop, *, wait_timeout):
            cleanup_started.set()
            await cleanup_release.wait()
            terminated.append((process_to_stop, wait_timeout))
            cleanup_finished.set()

        monkeypatch.setattr(shell_runtime_module.os, "name", "nt", raising=False)
        monkeypatch.setattr(
            shell_runtime_module.asyncio,
            "create_subprocess_exec",
            fake_create_subprocess_exec,
        )
        monkeypatch.setattr(shell_runtime_module, "attach_process_tree", lambda candidate: True)
        monkeypatch.setattr(shell_runtime_module, "_STARTUP_CLEANUP_TASKS", set())
        monkeypatch.setattr(
            shell_runtime_module,
            "terminate_process_tree",
            fake_terminate_process_tree,
        )

        startup = asyncio.create_task(
            shell_runtime_module.start_shell_process(
                "echo maybe-started",
                cwd=None,
                output_chunks=[],
            )
        )
        await asyncio.wait_for(drain_started.wait(), timeout=1)
        startup.cancel()
        await asyncio.wait_for(cleanup_started.wait(), timeout=1)
        startup.cancel()

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(startup, timeout=1)

        assert process.stdin.closed is True
        assert cleanup_finished.is_set() is False
        cleanup_release.set()
        await asyncio.wait_for(cleanup_finished.wait(), timeout=1)
        await asyncio.sleep(0)
        assert terminated == [(process, shell_runtime_module._STARTUP_CLEANUP_WAIT_SECONDS)]
        assert shell_runtime_module._STARTUP_CLEANUP_TASKS == set()

    asyncio.run(run())


def test_windows_exec_process_sends_argv_only_after_job_attachment(monkeypatch):
    stdin = _FakeStdin()
    process = _FakeWindowsProcess(pid=988, stdin=stdin)
    attached = []

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        assert attached == []
        return process

    def fake_attach(candidate):
        attached.append(candidate)
        return True

    monkeypatch.setattr(shell_runtime_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(shell_runtime_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shell_runtime_module, "attach_process_tree", fake_attach)

    started = asyncio.run(
        shell_runtime_module.start_exec_process(
            ["python", "-m", "pytest", "path with spaces"],
            cwd="C:/workspace",
        )
    )

    assert started is process
    assert attached == [process]
    assert stdin.closed is True
    assert stdin.writes == [
        b'{"argv": ["python", "-m", "pytest", "path with spaces"]}\n'
    ]


def test_windows_launcher_executes_argv_without_shell_reparsing(monkeypatch):
    class FakeInput:
        buffer = io.BytesIO(b'{"argv":["python","-m","pytest","path with spaces"]}\n')

    class Completed:
        returncode = 7

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setattr(windows_launcher_module.sys, "stdin", FakeInput())
    monkeypatch.setattr(windows_launcher_module.subprocess, "run", fake_run)

    assert windows_launcher_module.main() == 7
    assert calls == [
        (
            ["python", "-m", "pytest", "path with spaces"],
            {
                "shell": False,
                "stdin": windows_launcher_module.subprocess.DEVNULL,
                "check": False,
            },
        )
    ]


def test_drain_process_output_cancels_tasks_on_timeout():
    async def sleeper():
        await asyncio.sleep(1)

    async def run():
        task = asyncio.create_task(sleeper())
        drained = await shell_runtime_module.drain_process_output([task], timeout=0.01)
        return drained, task.cancelled()

    drained, was_cancelled = asyncio.run(run())

    assert drained is False
    assert was_cancelled is True


def test_format_captured_output_preserves_order_and_prefixes_stderr():
    output = shell_runtime_module.format_captured_output(
        [
            shell_runtime_module.CapturedOutputChunk("stdout", b"out1\n"),
            shell_runtime_module.CapturedOutputChunk("stderr", b"err1\nerr2\n"),
            shell_runtime_module.CapturedOutputChunk("stdout", b"out2"),
        ]
    )

    assert output == "out1\n[stderr] err1\n[stderr] err2\nout2"


def test_format_captured_output_returns_placeholder_and_truncates():
    assert shell_runtime_module.format_captured_output([]) == "(no output)"

    long_text = "x" * 20
    output = shell_runtime_module.format_captured_output(
        [shell_runtime_module.CapturedOutputChunk("stdout", long_text.encode("utf-8"))],
        max_chars=10,
    )

    assert output.startswith("x" * 10)
    assert "truncated, total 20 chars" in output
