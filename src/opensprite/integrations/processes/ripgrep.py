"""Runtime adapter for invoking ripgrep inside a workspace."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from .subprocess_control import windows_hidden_process_kwargs


def find_ripgrep() -> str | None:
    """Return the ripgrep executable path when it is available."""
    return shutil.which("rg")


async def run_ripgrep(
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: float,
) -> tuple[int, str, str]:
    """Run ripgrep without a shell and return decoded process output."""
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **windows_hidden_process_kwargs(),
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        return 124, stdout_bytes.decode("utf-8", errors="replace"), stderr_text or "ripgrep timed out"
    return (
        int(process.returncode or 0),
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )
