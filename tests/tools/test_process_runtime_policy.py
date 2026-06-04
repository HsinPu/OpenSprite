from opensprite.tools.process_runtime_policy import (
    PROCESS_LOST_ON_STARTUP_POLICY,
    PROCESS_REATTACH_RUNTIME_LOCAL_REASON,
    PROCESS_RECOVERY_RUNTIME_RESTART_REASON,
    PROCESS_TERMINATION_CANCELLED,
    PROCESS_TERMINATION_ERROR,
    PROCESS_TERMINATION_EXIT,
    PROCESS_TERMINATION_KILLED,
    PROCESS_TERMINATION_RUNTIME_RESTART,
    PROCESS_TERMINATION_SHUTDOWN,
    PROCESS_TERMINATION_TIMEOUT,
    PROCESS_TERMINATION_UNKNOWN,
)


def test_process_runtime_termination_reasons_are_stable():
    assert PROCESS_TERMINATION_RUNTIME_RESTART == "runtime_restart"
    assert PROCESS_TERMINATION_EXIT == "exit"
    assert PROCESS_TERMINATION_TIMEOUT == "timeout"
    assert PROCESS_TERMINATION_CANCELLED == "cancelled"
    assert PROCESS_TERMINATION_ERROR == "error"
    assert PROCESS_TERMINATION_KILLED == "killed"
    assert PROCESS_TERMINATION_SHUTDOWN == "shutdown"
    assert PROCESS_TERMINATION_UNKNOWN == "unknown"


def test_process_runtime_recovery_metadata_markers_are_stable():
    assert PROCESS_RECOVERY_RUNTIME_RESTART_REASON == PROCESS_TERMINATION_RUNTIME_RESTART
    assert PROCESS_REATTACH_RUNTIME_LOCAL_REASON == "stdout_stderr_and_watch_state_are_runtime_local"
    assert PROCESS_LOST_ON_STARTUP_POLICY == "mark_running_processes_lost_on_startup"
