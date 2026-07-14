"""Process lifecycle helpers shared across the codebase."""

import asyncio
import contextlib
import os
import signal
import subprocess
import weakref
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _WindowsJobRegistration:
    handle: Any
    process: asyncio.subprocess.Process


_WINDOWS_JOB_HANDLES: dict[int, _WindowsJobRegistration] = {}
_WINDOWS_JOB_WATCHERS: set[asyncio.Task[None]] = set()
_WINDOWS_TERMINATION_TASKS: weakref.WeakKeyDictionary[
    asyncio.subprocess.Process,
    asyncio.Task[None],
] = weakref.WeakKeyDictionary()
_WINDOWS_ROOT_EXIT_POLL_INTERVAL = 0.05
_POSIX_GROUP_EXIT_POLL_INTERVAL = 0.05
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100


def _close_windows_handle(handle: Any) -> None:
    if os.name != "nt" or not handle:
        return
    try:
        import ctypes
        from ctypes import wintypes

        close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        close_handle(handle)
    except (AttributeError, OSError):
        return


def _create_windows_kill_job(pid: int) -> Any | None:
    """Create a kill-on-close Job Object and assign one process to it."""
    if os.name != "nt":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_job = kernel32.CreateJobObjectW
        create_job.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        create_job.restype = wintypes.HANDLE
        set_job_info = kernel32.SetInformationJobObject
        set_job_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        set_job_info.restype = wintypes.BOOL
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        assign_process = kernel32.AssignProcessToJobObject
        assign_process.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        assign_process.restype = wintypes.BOOL

        job_handle = create_job(None, None)
        if not job_handle:
            return None
        limits = _ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not set_job_info(
            job_handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            _close_windows_handle(job_handle)
            return None

        process_handle = open_process(_PROCESS_TERMINATE | _PROCESS_SET_QUOTA, False, int(pid))
        if not process_handle:
            _close_windows_handle(job_handle)
            return None
        try:
            if not assign_process(job_handle, process_handle):
                _close_windows_handle(job_handle)
                return None
        finally:
            _close_windows_handle(process_handle)
        return job_handle
    except (AttributeError, OSError, ValueError):
        return None


def _release_windows_job(
    pid: int,
    *,
    terminate: bool,
    expected_registration: _WindowsJobRegistration | None = None,
) -> bool:
    normalized_pid = int(pid)
    registration = _WINDOWS_JOB_HANDLES.get(normalized_pid)
    if registration is None:
        return False
    if expected_registration is not None and registration is not expected_registration:
        return False

    del _WINDOWS_JOB_HANDLES[normalized_pid]
    handle = registration.handle
    try:
        if terminate:
            import ctypes
            from ctypes import wintypes

            terminate_job = ctypes.WinDLL("kernel32", use_last_error=True).TerminateJobObject
            terminate_job.argtypes = [wintypes.HANDLE, wintypes.UINT]
            terminate_job.restype = wintypes.BOOL
            terminate_job(handle, 1)
    except (AttributeError, OSError):
        pass
    finally:
        _close_windows_handle(handle)
    return True


def attach_process_tree(process: asyncio.subprocess.Process) -> bool:
    """Attach a Windows subprocess tree to a kill-on-close Job Object."""
    if os.name != "nt":
        return False
    handle = _create_windows_kill_job(process.pid)
    if handle is None:
        return False

    registration = _WindowsJobRegistration(handle=handle, process=process)
    old_registration = _WINDOWS_JOB_HANDLES.pop(process.pid, None)
    if old_registration is not None:
        _close_windows_handle(old_registration.handle)
    _WINDOWS_JOB_HANDLES[process.pid] = registration

    async def _release_after_exit() -> None:
        try:
            # On Windows, asyncio's Process.wait() can stay pending until all
            # inherited stdout/stderr pipe handles close, even though the root
            # process has exited and returncode is already available.  Observe
            # the root directly so closing the Job kills those descendants and
            # lets the pipe readers finish.
            while process.returncode is None:
                await asyncio.sleep(_WINDOWS_ROOT_EXIT_POLL_INTERVAL)
        finally:
            _release_windows_job(
                process.pid,
                terminate=False,
                expected_registration=registration,
            )

    watcher = asyncio.create_task(_release_after_exit())
    _WINDOWS_JOB_WATCHERS.add(watcher)

    def _consume_result(completed: asyncio.Task[None]) -> None:
        _WINDOWS_JOB_WATCHERS.discard(completed)
        with contextlib.suppress(BaseException):
            completed.result()

    watcher.add_done_callback(_consume_result)
    return True


def windows_hidden_process_kwargs(*, new_process_group: bool = False) -> dict[str, Any]:
    """Return Windows subprocess kwargs that suppress console windows."""
    if os.name != "nt":
        return {}

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if new_process_group:
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    kwargs: dict[str, Any] = {"creationflags": creationflags}
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_type is not None:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    return kwargs


def detached_process_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return windows_hidden_process_kwargs(new_process_group=True)
    return {"start_new_session": True}


async def _wait_for_process_exit(process: asyncio.subprocess.Process, *, wait_timeout: float) -> bool:
    """Wait for a process to exit, returning False on timeout."""
    if process.returncode is not None:
        return True

    try:
        # On Windows the subprocess transport reuses its exit waiter.  Letting
        # wait_for cancel that waiter poisons later cleanup attempts, which can
        # then raise CancelledError instead of waiting for termination.
        await asyncio.wait_for(asyncio.shield(process.wait()), timeout=wait_timeout)
        return True
    except asyncio.TimeoutError:
        return process.returncode is not None


def _signal_unix_process_tree(process: asyncio.subprocess.Process, sig: int) -> None:
    """Send a Unix signal to the process group, falling back to the direct process."""
    try:
        os.killpg(process.pid, sig)
        return
    except ProcessLookupError:
        return
    except Exception:
        pass

    try:
        if sig == signal.SIGTERM:
            process.terminate()
        else:
            process.kill()
    except ProcessLookupError:
        return
    except Exception:
        return


def _unix_process_group_exists(pid: int) -> bool:
    """Return whether a POSIX process group still has at least one member."""
    try:
        os.killpg(int(pid), 0)
    except ProcessLookupError:
        return False
    except Exception:
        # Permission and transient OS errors do not prove that the group is
        # gone. Treat them as alive so cleanup remains fail-safe.
        return True
    return True


async def _wait_for_unix_process_group_exit(pid: int, *, wait_timeout: float) -> bool:
    """Wait for the complete POSIX process group, not just its leader, to exit."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, wait_timeout)
    while _unix_process_group_exists(pid):
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(_POSIX_GROUP_EXIT_POLL_INTERVAL, remaining))
    return True


async def _terminate_windows_process_tree_once(
    process: asyncio.subprocess.Process,
    *,
    wait_timeout: float,
) -> None:
    """Terminate one Windows process identity without PID-only fallbacks."""
    registration = _WINDOWS_JOB_HANDLES.get(int(process.pid))
    if registration is not None and registration.process is not process:
        # The PID now belongs to a newer process generation.  The old asyncio
        # Process may not have observed its exit yet, so never touch the PID.
        return
    if (
        registration is not None
        and _release_windows_job(
            process.pid,
            terminate=True,
            expected_registration=registration,
        )
    ):
        await _wait_for_process_exit(process, wait_timeout=wait_timeout)
        return
    if process.returncode is not None:
        return

    # An unregistered process has no trustworthy PID-generation proof.  Kill
    # through asyncio's retained process handle instead of invoking taskkill by
    # PID, which could target an unrelated replacement process after PID reuse.
    with contextlib.suppress(ProcessLookupError):
        process.kill()
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(process.wait()), timeout=wait_timeout)


async def terminate_process_tree(
    process: asyncio.subprocess.Process,
    *,
    wait_timeout: float = 5,
) -> None:
    """Best-effort terminate a process and its descendants."""
    if os.name == "nt":
        termination_task = _WINDOWS_TERMINATION_TASKS.get(process)
        if termination_task is None:
            termination_task = asyncio.create_task(
                _terminate_windows_process_tree_once(process, wait_timeout=wait_timeout)
            )
            _WINDOWS_TERMINATION_TASKS[process] = termination_task
        # Keep the identity-bound cleanup alive if one of several callers is
        # cancelled.  Later callers await the same operation instead of issuing
        # another PID-based termination after the Job registration is released.
        await asyncio.shield(termination_task)
        return

    if process.returncode is not None:
        # The process-group leader may already be gone while descendants are
        # still alive.  A final group kill remains valid on POSIX and avoids
        # leaking children that inherited the command's pipes.
        _signal_unix_process_tree(process, signal.SIGKILL)
        return

    _signal_unix_process_tree(process, signal.SIGTERM)

    if await _wait_for_unix_process_group_exit(process.pid, wait_timeout=wait_timeout):
        await _wait_for_process_exit(process, wait_timeout=wait_timeout)
        return

    _signal_unix_process_tree(process, signal.SIGKILL)

    await _wait_for_unix_process_group_exit(process.pid, wait_timeout=wait_timeout)
    if await _wait_for_process_exit(process, wait_timeout=wait_timeout):
        return

    with contextlib.suppress(ProcessLookupError):
        process.kill()
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(process.wait()), timeout=wait_timeout)
