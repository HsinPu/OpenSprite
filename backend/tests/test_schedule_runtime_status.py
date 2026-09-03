from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

from opensprite_backend.schedules.runtime_status import detect_schedule_runtime_status


def test_windows_reports_login_only_continuity() -> None:
    with patch("platform.system", return_value="Windows"):
        status = detect_schedule_runtime_status()
    assert (status.platform, status.continuity) == ("windows", "login_only")


def test_linux_reports_linger_only_when_loginctl_confirms_it() -> None:
    with (
        patch("platform.system", return_value="Linux"),
        patch(
            "subprocess.run",
            return_value=CompletedProcess([], 0, stdout="yes\n", stderr=""),
        ) as run,
    ):
        status = detect_schedule_runtime_status()
    assert status.continuity == "linger_enabled"
    assert run.call_args.kwargs["shell"] is False

    with (
        patch("platform.system", return_value="Linux"),
        patch(
            "subprocess.run",
            return_value=CompletedProcess([], 1, stdout="", stderr="denied"),
        ),
    ):
        assert detect_schedule_runtime_status().continuity == "unknown"
