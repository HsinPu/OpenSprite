"""Best-effort schedule continuity status without changing host configuration."""

from __future__ import annotations

from dataclasses import dataclass
import platform
import subprocess


@dataclass(frozen=True, slots=True)
class ScheduleRuntimeStatus:
    platform: str
    continuity: str


def detect_schedule_runtime_status() -> ScheduleRuntimeStatus:
    system = platform.system().lower()
    if system == "windows":
        return ScheduleRuntimeStatus("windows", "login_only")
    if system != "linux":
        return ScheduleRuntimeStatus(system or "unknown", "unknown")
    try:
        completed = subprocess.run(
            ["loginctl", "show-user", "--property=Linger", "--value"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ScheduleRuntimeStatus("linux", "unknown")
    if completed.returncode != 0:
        return ScheduleRuntimeStatus("linux", "unknown")
    continuity = (
        "linger_enabled"
        if completed.stdout.strip().lower() == "yes"
        else "login_only"
    )
    return ScheduleRuntimeStatus("linux", continuity)
