import asyncio
import subprocess

from opensprite.utils import processes as processes_module


class _FakeProcess:
    def __init__(self, *, pid: int = 123, wait_plan: list[str] | None = None):
        self.pid = pid
        self.wait_plan = list(wait_plan or ["exit"])
        self.returncode = None
        self.kill_called = False
        self.terminate_called = False
        self.wait_calls = 0

    async def wait(self):
        self.wait_calls += 1
        if self.returncode is not None:
            return self.returncode

        action = self.wait_plan.pop(0) if self.wait_plan else "exit"
        if action == "timeout":
            await asyncio.sleep(1)
            return self.returncode

        if self.kill_called:
            self.returncode = -9
            return self.returncode

        self.returncode = 0
        return self.returncode

    def kill(self):
        self.kill_called = True
        self.returncode = -9

    def terminate(self):
        self.terminate_called = True
        self.returncode = 0


def test_windows_hidden_process_kwargs_suppresses_console_window(monkeypatch):
    monkeypatch.setattr(processes_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(processes_module.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(processes_module.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200, raising=False)

    kwargs = processes_module.windows_hidden_process_kwargs(new_process_group=True)

    assert kwargs["creationflags"] & 0x08000000
    assert kwargs["creationflags"] & 0x00000200
    if getattr(subprocess, "STARTUPINFO", None) is not None:
        assert "startupinfo" in kwargs


def test_unregistered_windows_process_uses_identity_bound_handle_kill(monkeypatch):
    process = _FakeProcess(pid=456)

    monkeypatch.setattr(processes_module.os, "name", "nt", raising=False)

    asyncio.run(processes_module.terminate_process_tree(process, wait_timeout=0.01))

    assert process.returncode == -9
    assert process.kill_called is True


def test_terminate_process_tree_releases_windows_job_after_root_exits(monkeypatch):
    released_jobs = []
    process = _FakeProcess(pid=321)
    process.returncode = 0
    registration = processes_module._WindowsJobRegistration(
        handle=object(),
        process=process,
    )

    def fake_release_windows_job(pid, *, terminate, expected_registration=None):
        released_jobs.append((pid, terminate, expected_registration))
        return True

    monkeypatch.setattr(processes_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(processes_module, "_WINDOWS_JOB_HANDLES", {321: registration})
    monkeypatch.setattr(processes_module, "_release_windows_job", fake_release_windows_job)

    asyncio.run(processes_module.terminate_process_tree(process, wait_timeout=0.01))

    assert released_jobs == [(321, True, registration)]
    assert process.kill_called is False


def test_windows_job_watcher_does_not_release_reused_pid_registration(monkeypatch):
    async def run() -> None:
        first_handle = object()
        second_handle = object()
        handles = iter((first_handle, second_handle))
        closed_handles = []

        class _GenerationProcess:
            pid = 777

            def __init__(self):
                self.returncode = None

            async def wait(self):
                return self.returncode

        monkeypatch.setattr(processes_module.os, "name", "nt", raising=False)
        monkeypatch.setattr(processes_module, "_WINDOWS_JOB_HANDLES", {})
        monkeypatch.setattr(processes_module, "_WINDOWS_JOB_WATCHERS", set())
        monkeypatch.setattr(
            processes_module,
            "_create_windows_kill_job",
            lambda pid: next(handles),
        )
        monkeypatch.setattr(
            processes_module,
            "_close_windows_handle",
            closed_handles.append,
        )

        first_process = _GenerationProcess()
        second_process = _GenerationProcess()

        assert processes_module.attach_process_tree(first_process) is True
        first_watcher = next(iter(processes_module._WINDOWS_JOB_WATCHERS))

        # The first root has exited, but its watcher has not run before Windows
        # reuses the PID for a newly attached process.
        first_process.returncode = 0
        assert processes_module.attach_process_tree(second_process) is True
        second_watcher = next(
            watcher
            for watcher in processes_module._WINDOWS_JOB_WATCHERS
            if watcher is not first_watcher
        )

        await first_watcher

        current = processes_module._WINDOWS_JOB_HANDLES[777]
        assert current.handle is second_handle
        assert closed_handles == [first_handle]

        second_process.returncode = 0
        await second_watcher

        assert processes_module._WINDOWS_JOB_HANDLES == {}
        assert closed_handles == [first_handle, second_handle]

    asyncio.run(run())


def test_terminate_process_tree_does_not_terminate_reused_pid_registration(monkeypatch):
    async def run() -> None:
        first_handle = object()
        second_handle = object()
        handles = iter((first_handle, second_handle))
        closed_handles = []

        class _GenerationProcess:
            pid = 778

            def __init__(self):
                self.returncode = None

            async def wait(self):
                return self.returncode

        monkeypatch.setattr(processes_module.os, "name", "nt", raising=False)
        monkeypatch.setattr(processes_module, "_WINDOWS_JOB_HANDLES", {})
        monkeypatch.setattr(processes_module, "_WINDOWS_JOB_WATCHERS", set())
        monkeypatch.setattr(
            processes_module,
            "_create_windows_kill_job",
            lambda pid: next(handles),
        )
        monkeypatch.setattr(
            processes_module,
            "_close_windows_handle",
            closed_handles.append,
        )

        first_process = _GenerationProcess()
        second_process = _GenerationProcess()

        assert processes_module.attach_process_tree(first_process) is True
        first_process.returncode = 0
        assert processes_module.attach_process_tree(second_process) is True

        # Cleanup for the old process must not terminate the newer Job Object
        # that happens to have the same reused PID.
        await processes_module.terminate_process_tree(first_process, wait_timeout=0.01)

        current = processes_module._WINDOWS_JOB_HANDLES[778]
        assert current.handle is second_handle
        assert closed_handles == [first_handle]

        second_process.returncode = 0
        await asyncio.gather(*tuple(processes_module._WINDOWS_JOB_WATCHERS))

        assert processes_module._WINDOWS_JOB_HANDLES == {}
        assert closed_handles == [first_handle, second_handle]

    asyncio.run(run())


def test_terminate_process_tree_does_not_touch_reused_pid_before_old_returncode_updates(monkeypatch):
    async def run() -> None:
        handles = iter((object(), object()))

        class _GenerationProcess:
            pid = 779

            def __init__(self):
                self.returncode = None

            async def wait(self):
                return self.returncode

        monkeypatch.setattr(processes_module.os, "name", "nt", raising=False)
        monkeypatch.setattr(processes_module, "_WINDOWS_JOB_HANDLES", {})
        monkeypatch.setattr(processes_module, "_WINDOWS_JOB_WATCHERS", set())
        monkeypatch.setattr(processes_module, "_create_windows_kill_job", lambda pid: next(handles))
        monkeypatch.setattr(processes_module, "_close_windows_handle", lambda handle: None)

        first_process = _GenerationProcess()
        second_process = _GenerationProcess()

        assert processes_module.attach_process_tree(first_process) is True
        assert processes_module.attach_process_tree(second_process) is True

        # Windows may reuse the PID before asyncio dispatches the old process's
        # exit callback.  Cleanup for that stale object must still leave the new
        # process generation alone.
        await processes_module.terminate_process_tree(first_process, wait_timeout=0.01)

        assert processes_module._WINDOWS_JOB_HANDLES[779].process is second_process

        first_process.returncode = 0
        second_process.returncode = 0
        await asyncio.gather(*tuple(processes_module._WINDOWS_JOB_WATCHERS))

    asyncio.run(run())


def test_concurrent_windows_termination_reuses_one_identity_bound_cleanup(monkeypatch):
    async def run() -> None:
        release_wait = asyncio.Event()
        release_calls = []

        class _BlockingProcess:
            pid = 780

            def __init__(self):
                self.returncode = None
                self.kill_calls = 0

            async def wait(self):
                await release_wait.wait()
                self.returncode = -9
                return self.returncode

            def kill(self):
                self.kill_calls += 1

        process = _BlockingProcess()
        registration = processes_module._WindowsJobRegistration(handle=object(), process=process)

        def fake_release(pid, *, terminate, expected_registration=None):
            release_calls.append((pid, terminate, expected_registration))
            processes_module._WINDOWS_JOB_HANDLES.pop(pid, None)
            return True

        monkeypatch.setattr(processes_module.os, "name", "nt", raising=False)
        monkeypatch.setattr(processes_module, "_WINDOWS_JOB_HANDLES", {780: registration})
        monkeypatch.setattr(processes_module, "_WINDOWS_TERMINATION_TASKS", {})
        monkeypatch.setattr(processes_module, "_release_windows_job", fake_release)

        first = asyncio.create_task(processes_module.terminate_process_tree(process, wait_timeout=0.2))
        await asyncio.sleep(0)
        second = asyncio.create_task(processes_module.terminate_process_tree(process, wait_timeout=0.2))
        await asyncio.sleep(0)

        assert release_calls == [(780, True, registration)]
        assert process.kill_calls == 0

        release_wait.set()
        await asyncio.gather(first, second)

        assert release_calls == [(780, True, registration)]
        assert process.kill_calls == 0

    asyncio.run(run())


def test_terminate_process_tree_stops_after_sigterm_when_process_exits(monkeypatch):
    killpg_calls = []
    process = _FakeProcess(pid=789)
    group_exists = True

    def fake_killpg(pid, sig):
        nonlocal group_exists
        if sig == 0:
            if group_exists:
                return
            raise ProcessLookupError
        killpg_calls.append((pid, sig))
        if sig == processes_module.signal.SIGTERM:
            process.returncode = 0
            group_exists = False

    monkeypatch.setattr(processes_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(processes_module.os, "killpg", fake_killpg, raising=False)
    monkeypatch.setattr(processes_module.signal, "SIGTERM", "SIGTERM", raising=False)
    monkeypatch.setattr(processes_module.signal, "SIGKILL", "SIGKILL", raising=False)

    asyncio.run(processes_module.terminate_process_tree(process, wait_timeout=0.01))

    assert killpg_calls == [(789, processes_module.signal.SIGTERM)]
    assert process.kill_called is False


def test_terminate_process_tree_kills_descendant_after_sigterm_leader_exit(monkeypatch):
    killpg_calls = []
    process = _FakeProcess(pid=790)
    group_exists = True

    def fake_killpg(pid, sig):
        nonlocal group_exists
        if sig == 0:
            if group_exists:
                return
            raise ProcessLookupError
        killpg_calls.append((pid, sig))
        if sig == processes_module.signal.SIGTERM:
            # The leader exits, but a descendant ignores SIGTERM and keeps the
            # process group alive.
            process.returncode = 0
        elif sig == processes_module.signal.SIGKILL:
            group_exists = False

    monkeypatch.setattr(processes_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(processes_module.os, "killpg", fake_killpg, raising=False)
    monkeypatch.setattr(processes_module.signal, "SIGTERM", "SIGTERM", raising=False)
    monkeypatch.setattr(processes_module.signal, "SIGKILL", "SIGKILL", raising=False)

    asyncio.run(processes_module.terminate_process_tree(process, wait_timeout=0))

    assert killpg_calls == [
        (790, processes_module.signal.SIGTERM),
        (790, processes_module.signal.SIGKILL),
    ]
    assert process.kill_called is False


def test_terminate_process_tree_kills_posix_group_after_leader_exits(monkeypatch):
    killpg_calls = []
    process = _FakeProcess(pid=246)
    process.returncode = 0

    monkeypatch.setattr(processes_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(
        processes_module.os,
        "killpg",
        lambda pid, sig: killpg_calls.append((pid, sig)),
        raising=False,
    )
    monkeypatch.setattr(processes_module.signal, "SIGKILL", "SIGKILL", raising=False)

    asyncio.run(processes_module.terminate_process_tree(process, wait_timeout=0.01))

    assert killpg_calls == [(246, processes_module.signal.SIGKILL)]
    assert process.kill_called is False


def test_terminate_process_tree_escalates_from_sigterm_to_sigkill(monkeypatch):
    killpg_calls = []
    process = _FakeProcess(pid=987, wait_plan=["timeout"])
    group_exists = True

    def fake_killpg(pid, sig):
        nonlocal group_exists
        if sig == 0:
            if group_exists:
                return
            raise ProcessLookupError
        killpg_calls.append((pid, sig))
        if sig == processes_module.signal.SIGKILL:
            process.returncode = -9
            group_exists = False

    monkeypatch.setattr(processes_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(processes_module.os, "killpg", fake_killpg, raising=False)
    monkeypatch.setattr(processes_module.signal, "SIGTERM", "SIGTERM", raising=False)
    monkeypatch.setattr(processes_module.signal, "SIGKILL", "SIGKILL", raising=False)

    asyncio.run(processes_module.terminate_process_tree(process, wait_timeout=0.01))

    assert killpg_calls == [
        (987, processes_module.signal.SIGTERM),
        (987, processes_module.signal.SIGKILL),
    ]
    assert process.kill_called is False
    assert process.returncode == -9
