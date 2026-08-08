"""Shell execution tool."""

import asyncio
import re
from pathlib import Path
from typing import Any, Callable

from opensprite.core.contracts.tool_results import tool_error_result
from opensprite.modules.tools.shell_policy import (
    DEFAULT_EXEC_DENY_PATTERNS,
    classify_destructive_shell_command,
    dangerous_command_error,
    foreground_exec_guidance,
    is_help_or_version_command,
)
from opensprite.integrations.processes.background_runtime import (
    BackgroundProcessManager,
    BackgroundSession,
    SessionExitNotifier,
)
from opensprite.integrations.processes.shell_runtime import (
    CapturedOutputChunk,
    drain_process_output,
    format_captured_output,
    start_shell_process,
)
from opensprite.integrations.processes.subprocess_control import terminate_process_tree
from opensprite.integrations.workspace.paths import build_workspace_resolver
from opensprite.modules.tools.base import Tool
from opensprite.modules.tools.validation import NON_EMPTY_STRING_PATTERN


WorkspaceResolver = Callable[[], Path]
BackgroundNotificationFactory = Callable[[], SessionExitNotifier | None]
BackgroundSessionOwnerFactory = Callable[[], dict[str, str | None] | None]
_CANCEL_CLEANUP_TASKS: set[asyncio.Task[None]] = set()


def _track_cancel_cleanup(task: asyncio.Task[None]) -> None:
    """Keep cancellation cleanup alive if the caller is cancelled again."""
    _CANCEL_CLEANUP_TASKS.add(task)

    def _consume_result(completed: asyncio.Task[None]) -> None:
        _CANCEL_CLEANUP_TASKS.discard(completed)
        try:
            completed.result()
        except BaseException:
            pass

    task.add_done_callback(_consume_result)


def _build_background_session_result(
    session: BackgroundSession,
    output: str,
    *,
    yield_ms: int | None,
) -> str:
    """Build the response returned when exec moves a command into the background."""
    if yield_ms is None:
        heading = "Background session started."
    else:
        heading = f"Command is still running after {yield_ms}ms; moved to background."

    return "\n".join(
        [
            heading,
            f"Session ID: {session.session_id}",
            f"Status: {session.state}",
            f"PID: {session.pid}",
            *(
                [f"Owner: {session.owner_session_id or '-'} / {session.owner_run_id or '-'}"]
                if session.owner_session_id or session.owner_run_id
                else []
            ),
            "Use process with action=\"poll\" to inspect it or action=\"kill\" to stop it.",
            "Current output:",
            output,
        ]
    )


def _build_timeout_result(timeout: int, output: str, *, drained: bool) -> str:
    """Build the timeout response for exec output collection."""
    if not drained:
        output += (
            "\n\n[exec] Warning: output pipes did not close promptly after timeout; "
            "a descendant process may still have inherited stdout/stderr."
        )

    return tool_error_result(
        (
            f"Command timed out after {timeout}s. "
            "The command may be waiting for interactive input or may be stuck. "
            f"Partial output before timeout:\n{output}"
        ),
        error_type="ToolExecutionError",
        category="timeout",
        repeated_error_key=f"exec:timeout:{timeout}",
        metadata={"tool_name": "exec", "timeout_seconds": timeout},
    )


def _build_pipe_drain_warning_result(output: str, *, drain_timeout: int) -> str:
    """Build the warning shown when output pipes stay open after exit."""
    return (
        f"{output}\n\n"
        f"[exec] Warning: output pipes did not close within {drain_timeout}s after "
        "the shell exited. A background process may still be writing to the same "
        "stdout/stderr as the shell. Redirect long-running servers to a file or "
        "/dev/null, or run them outside exec."
    )


class ExecTool(Tool):
    """Tool to execute shell commands."""

    MAX_COMMAND_LENGTH = 2000
    DENY_PATTERNS = DEFAULT_EXEC_DENY_PATTERNS

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        workspace_resolver: WorkspaceResolver | None = None,
        timeout: int = 60,
        deny_patterns: list[str] | None = None,
        process_manager: BackgroundProcessManager | None = None,
        background_notification_factory: BackgroundNotificationFactory | None = None,
        background_session_owner_factory: BackgroundSessionOwnerFactory | None = None,
        notify_on_exit: bool = True,
        notify_on_exit_empty_success: bool = False,
    ):
        self._workspace_resolver = build_workspace_resolver(workspace, workspace_resolver)
        self.timeout = timeout
        self.deny_patterns = deny_patterns or self.DENY_PATTERNS
        self.process_manager = process_manager or BackgroundProcessManager()
        self._background_notification_factory = background_notification_factory
        self._background_session_owner_factory = background_session_owner_factory
        self.notify_on_exit = notify_on_exit
        self.notify_on_exit_empty_success = notify_on_exit_empty_success

    def _get_workspace(self) -> Path:
        return self._workspace_resolver()

    @staticmethod
    def _output_drain_timeout(timeout_seconds: float) -> float:
        return max(5.0, min(30.0, float(timeout_seconds)))

    def _validate_command(
        self,
        command: str,
        *,
        allow_managed_background: bool,
    ) -> str | None:
        if is_help_or_version_command(command):
            return None

        destructive_reason = classify_destructive_shell_command(command)
        if destructive_reason:
            return dangerous_command_error(destructive_reason)

        for pattern in self.deny_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return dangerous_command_error()

        guidance = foreground_exec_guidance(
            command,
            allow_long_lived=allow_managed_background,
        )
        if guidance is not None:
            return tool_error_result(
                guidance,
                error_type="ToolValidationError",
                category="invalid_arguments",
                invalid_arguments=True,
                metadata={"tool_name": self.name, "command_policy": "foreground_exec"},
            )

        return None

    async def _handle_timed_out_process(
        self,
        process: asyncio.subprocess.Process,
        read_tasks: list[asyncio.Task[None]],
        output_chunks: list[CapturedOutputChunk],
        *,
        timeout_seconds: int,
    ) -> str:
        await terminate_process_tree(process)
        drained = await drain_process_output(
            read_tasks,
            timeout=self._output_drain_timeout(timeout_seconds),
        )
        return _build_timeout_result(
            timeout_seconds,
            format_captured_output(output_chunks),
            drained=drained,
        )

    async def _handle_completed_process(
        self,
        process: asyncio.subprocess.Process,
        read_tasks: list[asyncio.Task[None]],
        output_chunks: list[CapturedOutputChunk],
        *,
        timeout_seconds: int,
    ) -> str:
        drain_timeout = self._output_drain_timeout(timeout_seconds)
        # The shell leader may exit after spawning descendants whose stdio is
        # inherited.  Finalize the managed group/job before waiting for those
        # descendants to close the command's output pipes.
        await terminate_process_tree(process)
        drained = await drain_process_output(read_tasks, timeout=drain_timeout)
        output = format_captured_output(output_chunks)
        if not drained:
            return _build_pipe_drain_warning_result(output, drain_timeout=drain_timeout)
        return output

    async def _cleanup_cancelled_process(
        self,
        process: asyncio.subprocess.Process | None,
        read_tasks: list[asyncio.Task[None]],
        *,
        timeout_seconds: int,
    ) -> None:
        if process is not None:
            await terminate_process_tree(process)
        if read_tasks:
            await drain_process_output(
                read_tasks,
                timeout=self._output_drain_timeout(timeout_seconds),
            )

    def _start_background_session(
        self,
        *,
        command: str,
        workspace: Path,
        process: asyncio.subprocess.Process,
        read_tasks: list[asyncio.Task[None]],
        output_chunks: list[CapturedOutputChunk],
        session_timeout_seconds: float | None,
        drain_timeout_seconds: float,
        yield_ms: int | None,
        notify_on_exit: bool,
        notify_on_exit_empty_success: bool,
    ) -> str:
        owner = self._background_session_owner_factory() if self._background_session_owner_factory is not None else None
        if not isinstance(owner, dict):
            owner = {}
        session = self.process_manager.register_session(
            command=command,
            cwd=str(workspace),
            process=process,
            read_tasks=read_tasks,
            output_chunks=output_chunks,
            timeout_seconds=session_timeout_seconds,
            drain_timeout=self._output_drain_timeout(drain_timeout_seconds),
            exit_notifier=(
                self._background_notification_factory()
                if self._background_notification_factory is not None
                else None
            ),
            notify_on_exit=notify_on_exit,
            notify_on_exit_empty_success=notify_on_exit_empty_success,
            owner_session_id=(
                str(owner.get("session_id"))
                if owner.get("session_id") is not None
                else None
            ),
            owner_run_id=(str(owner.get("run_id")) if owner.get("run_id") is not None else None),
            owner_channel=(str(owner.get("channel")) if owner.get("channel") is not None else None),
            owner_external_chat_id=(
                str(owner.get("external_chat_id"))
                if owner.get("external_chat_id") is not None
                else None
            ),
        )
        output = self.process_manager.render_output(session, max_chars=1200)
        return _build_background_session_result(session, output, yield_ms=yield_ms)

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return (
            "Execute one shell command inside the current workspace and return its output, "
            "or move it into a managed background session when requested."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Required. Full shell command to execute inside the current workspace.",
                    "pattern": NON_EMPTY_STRING_PATTERN,
                    "maxLength": self.MAX_COMMAND_LENGTH,
                },
                "background": {
                    "type": "boolean",
                    "description": "Optional. When true, start the command in a managed background session immediately.",
                },
                "yield_ms": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Optional. Wait this many milliseconds; if the command is still running, move it into a managed background session.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Optional. Override the foreground timeout in seconds. For background "
                        "sessions, also set a maximum runtime; omitted background sessions run "
                        "until they exit, are killed, or the agent shuts down."
                    ),
                },
                "notify_on_exit": {
                    "type": "boolean",
                    "description": "Optional. Override whether a managed background session should publish a completion notification when it exits.",
                },
                "notify_on_exit_empty_success": {
                    "type": "boolean",
                    "description": "Optional. Override whether successful managed background sessions with no output should still publish a completion notification.",
                }
            },
            "required": ["command"]
        }

    async def _execute(self, **kwargs: Any) -> str:
        command = str(kwargs["command"]).strip()
        background = bool(kwargs.get("background", False))
        yield_ms = kwargs.get("yield_ms")
        timeout_arg = kwargs.get("timeout_seconds")
        timeout_was_supplied = timeout_arg is not None
        timeout_seconds = int(timeout_arg if timeout_was_supplied else self.timeout)
        notify_arg = kwargs.get("notify_on_exit", self.notify_on_exit)
        notify_on_exit = bool(notify_arg)
        notify_on_exit_empty_success = bool(
            kwargs.get("notify_on_exit_empty_success", self.notify_on_exit_empty_success)
        )

        validation_error = self._validate_command(
            command,
            allow_managed_background=background or yield_ms is not None,
        )
        if validation_error is not None:
            return validation_error

        process: asyncio.subprocess.Process | None = None
        read_tasks: list[asyncio.Task[None]] = []
        try:
            workspace = self._get_workspace()
            output_chunks: list[CapturedOutputChunk] = []
            process, read_tasks = await start_shell_process(
                command,
                cwd=str(workspace),
                output_chunks=output_chunks,
            )

            if background:
                return self._start_background_session(
                    command=command,
                    workspace=workspace,
                    process=process,
                    read_tasks=read_tasks,
                    output_chunks=output_chunks,
                    session_timeout_seconds=(
                        float(timeout_seconds) if timeout_was_supplied else None
                    ),
                    drain_timeout_seconds=timeout_seconds,
                    yield_ms=None,
                    notify_on_exit=notify_on_exit,
                    notify_on_exit_empty_success=notify_on_exit_empty_success,
                )

            if yield_ms is not None:
                yield_timeout_seconds = yield_ms / 1000.0
                wait_timeout = min(float(timeout_seconds), yield_timeout_seconds)
                started_at = asyncio.get_running_loop().time()
                try:
                    await asyncio.wait_for(asyncio.shield(process.wait()), timeout=wait_timeout)
                except asyncio.TimeoutError:
                    elapsed = asyncio.get_running_loop().time() - started_at
                    if timeout_was_supplied and elapsed >= float(timeout_seconds):
                        return await self._handle_timed_out_process(
                            process,
                            read_tasks,
                            output_chunks,
                            timeout_seconds=timeout_seconds,
                        )
                    return self._start_background_session(
                        command=command,
                        workspace=workspace,
                        process=process,
                        read_tasks=read_tasks,
                        output_chunks=output_chunks,
                        session_timeout_seconds=(
                            max(0.001, float(timeout_seconds) - elapsed)
                            if timeout_was_supplied
                            else None
                        ),
                        drain_timeout_seconds=timeout_seconds,
                        yield_ms=yield_ms,
                        notify_on_exit=notify_on_exit,
                        notify_on_exit_empty_success=notify_on_exit_empty_success,
                    )

                return await self._handle_completed_process(
                    process,
                    read_tasks,
                    output_chunks,
                    timeout_seconds=timeout_seconds,
                )

            try:
                # Preserve the subprocess transport's exit waiter when this
                # tool task is cancelled so terminate_process_tree can still
                # finish cleanup reliably, especially on Windows.
                await asyncio.wait_for(asyncio.shield(process.wait()), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                return await self._handle_timed_out_process(
                    process,
                    read_tasks,
                    output_chunks,
                    timeout_seconds=timeout_seconds,
                )

            return await self._handle_completed_process(
                process,
                read_tasks,
                output_chunks,
                timeout_seconds=timeout_seconds,
            )
        except asyncio.CancelledError as cancel_error:
            cleanup_task = asyncio.create_task(
                self._cleanup_cancelled_process(
                    process,
                    read_tasks,
                    timeout_seconds=timeout_seconds,
                )
            )
            _track_cancel_cleanup(cleanup_task)
            try:
                await asyncio.shield(cleanup_task)
            except (asyncio.CancelledError, Exception):
                # A repeated cancel or cleanup failure must not replace the
                # original cancellation.  The tracked task keeps running.
                pass
            raise cancel_error
        except Exception as e:
            return tool_error_result(
                str(e),
                error_type="ToolExecutionError",
                metadata={"tool_name": self.name},
            )
