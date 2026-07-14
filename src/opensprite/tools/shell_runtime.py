"""Runtime helpers specific to exec-style shell command execution."""

import asyncio
import contextlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils.processes import (
    attach_process_tree,
    detached_process_kwargs,
    terminate_process_tree,
)


_WINDOWS_SHELL_LAUNCHER = Path(__file__).with_name("_windows_shell_launcher.py")
_STARTUP_CLEANUP_WAIT_SECONDS = 1.0
_STARTUP_CLEANUP_TASKS: set[asyncio.Task[None]] = set()


def _track_startup_cleanup(task: asyncio.Task[None]) -> None:
    """Keep launcher cleanup alive if its caller is cancelled again."""
    _STARTUP_CLEANUP_TASKS.add(task)

    def _consume_result(completed: asyncio.Task[None]) -> None:
        _STARTUP_CLEANUP_TASKS.discard(completed)
        with contextlib.suppress(BaseException):
            completed.result()

    task.add_done_callback(_consume_result)


async def _cleanup_windows_launcher(process: asyncio.subprocess.Process) -> None:
    if process.stdin is not None:
        with contextlib.suppress(Exception):
            process.stdin.close()
    await terminate_process_tree(process, wait_timeout=_STARTUP_CLEANUP_WAIT_SECONDS)


async def _start_windows_managed_process(
    payload: dict[str, Any],
    *,
    cwd: str | None,
) -> asyncio.subprocess.Process:
    """Release a command only after its launcher belongs to a Job Object."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        str(_WINDOWS_SHELL_LAUNCHER),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
        cwd=cwd,
        **_process_creation_kwargs(),
    )
    try:
        if not attach_process_tree(process):
            raise RuntimeError("Unable to attach Windows command launcher to a Job Object")
        if process.stdin is None:
            raise RuntimeError("Windows command launcher stdin is unavailable")
        encoded_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        process.stdin.write(encoded_payload)
        await process.stdin.drain()
        process.stdin.close()
    except BaseException:
        cleanup_task = asyncio.create_task(_cleanup_windows_launcher(process))
        _track_startup_cleanup(cleanup_task)
        try:
            await asyncio.shield(cleanup_task)
        except BaseException:
            # Preserve startup failure or cancellation. A second cancellation
            # cannot orphan the tracked cleanup task.
            pass
        raise
    return process


@dataclass(slots=True)
class CapturedOutputChunk:
    """One captured stdout/stderr chunk in arrival order."""

    stream_name: str
    data: bytes


def _append_stderr_text(text: str, result: list[str], needs_prefix: bool) -> bool:
    if not text:
        return needs_prefix

    for line in text.splitlines(keepends=True):
        if needs_prefix:
            result.append("[stderr] ")
        result.append(line)
        needs_prefix = line.endswith(("\n", "\r"))

    return needs_prefix


def format_captured_output(
    output_chunks: list[CapturedOutputChunk],
    *,
    max_chars: int | None = 3000,
    empty_placeholder: str = "(no output)",
) -> str:
    """Render captured stdout/stderr chunks into user-facing text."""
    result: list[str] = []
    stderr_needs_prefix = True

    for chunk in output_chunks:
        text = chunk.data.decode("utf-8", errors="replace")
        if chunk.stream_name == "stderr":
            stderr_needs_prefix = _append_stderr_text(text, result, stderr_needs_prefix)
        else:
            result.append(text)

    output = "".join(result).strip()
    if not output:
        output = empty_placeholder

    if max_chars is not None and len(output) > max_chars:
        output = output[:max_chars] + f"\n\n... (truncated, total {len(output)} chars)"

    return output


def _process_creation_kwargs() -> dict[str, Any]:
    return detached_process_kwargs()


async def _read_process_stream(
    stream: asyncio.StreamReader | None,
    *,
    stream_name: str,
    output_chunks: list[CapturedOutputChunk],
) -> None:
    if stream is None:
        return

    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return
        output_chunks.append(CapturedOutputChunk(stream_name=stream_name, data=chunk))


async def start_shell_process(
    command: str,
    *,
    cwd: str | None,
    output_chunks: list[CapturedOutputChunk],
) -> tuple[asyncio.subprocess.Process, list[asyncio.Task[None]]]:
    """Start a shell command with piped stdout/stderr collection."""
    if os.name == "nt":
        # Hold the command behind a stdin handshake until its launcher is in a
        # Job Object.  This closes the spawn/assignment race where an immediate
        # child could otherwise escape before the tree became managed.
        process = await _start_windows_managed_process({"command": command}, cwd=cwd)
    else:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=cwd,
            **_process_creation_kwargs(),
        )
    read_tasks = []
    if process.stdout is not None:
        read_tasks.append(
            asyncio.create_task(
                _read_process_stream(process.stdout, stream_name="stdout", output_chunks=output_chunks)
            )
        )
    if process.stderr is not None:
        read_tasks.append(
            asyncio.create_task(
                _read_process_stream(process.stderr, stream_name="stderr", output_chunks=output_chunks)
            )
        )
    return process, read_tasks


async def start_exec_process(
    command: list[str],
    *,
    cwd: str | None,
) -> asyncio.subprocess.Process:
    """Start an argv command with complete-tree ownership on each platform."""
    argv = [str(item) for item in command]
    if not argv or not argv[0].strip():
        raise ValueError("command argv cannot be empty")
    if os.name == "nt":
        return await _start_windows_managed_process({"argv": argv}, cwd=cwd)
    return await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        cwd=cwd,
        **_process_creation_kwargs(),
    )


async def drain_process_output(read_tasks: list[asyncio.Task[None]], *, timeout: float) -> bool:
    """Wait for output readers to finish, cancelling them on timeout."""
    try:
        await asyncio.wait_for(asyncio.gather(*read_tasks), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        for task in read_tasks:
            task.cancel()
        await asyncio.gather(*read_tasks, return_exceptions=True)
        return False
