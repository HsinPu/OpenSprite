"""In-memory background session management for exec/process tools."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Awaitable, Callable

from ..storage.base import StorageProvider, StoredBackgroundProcess
from ..utils.log import logger
from ..utils.processes import terminate_process_tree
from .shell_runtime import CapturedOutputChunk, drain_process_output, format_captured_output


SessionExitNotifier = Callable[["BackgroundSession"], Awaitable[None]]


@dataclass(slots=True)
class BackgroundSession:
    """One managed background shell session."""

    session_id: str
    command: str
    cwd: str | None
    process: asyncio.subprocess.Process
    read_tasks: list[asyncio.Task[None]]
    output_chunks: list[CapturedOutputChunk]
    timeout_seconds: float | None
    drain_timeout: float
    started_at: float = field(default_factory=time.monotonic)
    started_at_wall: float = field(default_factory=time.time)
    state: str = "running"
    termination_reason: str | None = None
    exit_code: int | None = None
    output_drained: bool = True
    error: str | None = None
    watch_task: asyncio.Task[None] | None = None
    last_polled_chars: int = 0
    finished_at: float | None = None
    finished_at_wall: float | None = None
    exit_notifier: SessionExitNotifier | None = None
    notify_on_exit: bool = True
    notify_on_exit_empty_success: bool = False
    suppress_exit_notification: bool = False
    owner_session_id: str | None = None
    owner_run_id: str | None = None
    owner_channel: str | None = None
    owner_external_chat_id: str | None = None
    output_path: str | None = None

    @property
    def pid(self) -> int:
        return self.process.pid


class BackgroundProcessManager:
    """Track background exec sessions for one agent runtime."""

    DEFAULT_MAX_EXITED_SESSIONS = 200

    def __init__(
        self,
        *,
        max_exited_sessions: int = DEFAULT_MAX_EXITED_SESSIONS,
        storage: StorageProvider | None = None,
    ) -> None:
        self._sessions: dict[str, BackgroundSession] = {}
        self.max_exited_sessions = max(1, int(max_exited_sessions))
        self.storage = storage

    def _prune_exited_sessions(self) -> None:
        exited_sessions = [
            session for session in self._sessions.values() if session.state == "exited"
        ]
        if len(exited_sessions) <= self.max_exited_sessions:
            return

        exited_sessions.sort(key=lambda session: session.finished_at or session.started_at)
        remove_count = len(exited_sessions) - self.max_exited_sessions
        for session in exited_sessions[:remove_count]:
            self._sessions.pop(session.session_id, None)

    def register_session(
        self,
        *,
        command: str,
        cwd: str | None,
        process: asyncio.subprocess.Process,
        read_tasks: list[asyncio.Task[None]],
        output_chunks: list[CapturedOutputChunk],
        timeout_seconds: float | None,
        drain_timeout: float,
        exit_notifier: SessionExitNotifier | None = None,
        notify_on_exit: bool = True,
        notify_on_exit_empty_success: bool = False,
        owner_session_id: str | None = None,
        owner_run_id: str | None = None,
        owner_channel: str | None = None,
        owner_external_chat_id: str | None = None,
    ) -> BackgroundSession:
        session = BackgroundSession(
            session_id=uuid.uuid4().hex[:12],
            command=command,
            cwd=cwd,
            process=process,
            read_tasks=read_tasks,
            output_chunks=output_chunks,
            timeout_seconds=(
                None if timeout_seconds is None else max(0.001, float(timeout_seconds))
            ),
            drain_timeout=max(0.001, float(drain_timeout)),
            exit_notifier=exit_notifier,
            notify_on_exit=notify_on_exit,
            notify_on_exit_empty_success=notify_on_exit_empty_success,
            owner_session_id=owner_session_id,
            owner_run_id=owner_run_id,
            owner_channel=owner_channel,
            owner_external_chat_id=owner_external_chat_id,
        )
        session.watch_task = asyncio.create_task(self._watch_session(session))
        self._sessions[session.session_id] = session
        self._schedule_persist_session(session, event_type="background_process.started")
        return session

    def _output_file_path_for_session(self, session: BackgroundSession) -> Path | None:
        if not session.cwd:
            return None
        return (
            Path(session.cwd)
            / ".opensprite"
            / "background-processes"
            / f"{session.session_id}.log"
        )

    def _persist_session_output(self, session: BackgroundSession) -> str | None:
        output_path = (
            Path(session.output_path)
            if session.output_path
            else self._output_file_path_for_session(session)
        )
        if output_path is None:
            return session.output_path
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                self.render_output(session, max_chars=None, empty_placeholder=""),
                encoding="utf-8",
            )
            session.output_path = str(output_path)
        except Exception:
            logger.exception(
                "background.process.output-persist-failed | session_id={}",
                session.session_id,
            )
        return session.output_path

    def _stored_process_for_session(
        self,
        session: BackgroundSession,
        *,
        output_path: str | None = None,
    ) -> StoredBackgroundProcess | None:
        if session.owner_session_id is None:
            return None
        return StoredBackgroundProcess(
            process_session_id=session.session_id,
            owner_session_id=session.owner_session_id,
            owner_run_id=session.owner_run_id,
            owner_channel=session.owner_channel,
            owner_external_chat_id=session.owner_external_chat_id,
            pid=session.pid,
            command=session.command,
            cwd=session.cwd,
            state=session.state,
            termination_reason=session.termination_reason,
            exit_code=session.exit_code,
            notify_mode="agent_summary" if session.notify_on_exit else "none",
            output_tail=self.render_output(session, max_chars=12000, empty_placeholder=""),
            output_path=output_path or session.output_path,
            metadata={
                "output_drained": session.output_drained,
                "notify_on_exit_empty_success": session.notify_on_exit_empty_success,
                "error": session.error,
            },
            started_at=session.started_at_wall,
            updated_at=session.finished_at_wall or time.time(),
            finished_at=session.finished_at_wall,
        )

    @staticmethod
    def _event_payload_for_process(process: StoredBackgroundProcess) -> dict[str, object]:
        return {
            "process_session_id": process.process_session_id,
            "command": process.command,
            "cwd": process.cwd,
            "pid": process.pid,
            "state": process.state,
            "termination_reason": process.termination_reason,
            "exit_code": process.exit_code,
            "notify_mode": process.notify_mode,
            "output_tail": process.output_tail,
            "output_path": process.output_path,
            "metadata": dict(process.metadata or {}),
        }

    async def _persist_stored_process(
        self,
        stored_process: StoredBackgroundProcess,
        *,
        event_type: str | None = None,
    ) -> StoredBackgroundProcess | None:
        if self.storage is None:
            return None
        try:
            persisted = await self.storage.upsert_background_process(stored_process)
            if persisted is not None and event_type and persisted.owner_run_id:
                run = await self.storage.get_run(persisted.owner_session_id, persisted.owner_run_id)
                if run is not None:
                    await self.storage.add_run_event(
                        persisted.owner_session_id,
                        persisted.owner_run_id,
                        event_type,
                        payload=self._event_payload_for_process(persisted),
                        created_at=persisted.updated_at,
                    )
            return persisted
        except Exception:
            logger.exception(
                "background.process.persist-failed | session_id={} state={}",
                stored_process.process_session_id,
                stored_process.state,
            )
            return None

    async def _persist_session(
        self,
        session: BackgroundSession,
        *,
        event_type: str | None = None,
    ) -> None:
        if self.storage is None or session.owner_session_id is None:
            return
        output_path = self._persist_session_output(session)
        stored_process = self._stored_process_for_session(session, output_path=output_path)
        if stored_process is None:
            return
        await self._persist_stored_process(stored_process, event_type=event_type)

    async def _add_session_run_event(
        self,
        session: BackgroundSession,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        if self.storage is None or session.owner_session_id is None or session.owner_run_id is None:
            return
        try:
            run = await self.storage.get_run(session.owner_session_id, session.owner_run_id)
            if run is None:
                return
            await self.storage.add_run_event(
                session.owner_session_id,
                session.owner_run_id,
                event_type,
                payload={
                    "process_session_id": session.session_id,
                    "command": session.command,
                    "cwd": session.cwd,
                    "termination_reason": session.termination_reason,
                    "exit_code": session.exit_code,
                    **payload,
                },
                created_at=time.time(),
            )
        except Exception:
            logger.exception(
                "background.process.event-persist-failed | session_id={} event_type={}",
                session.session_id,
                event_type,
            )

    def _schedule_persist_session(self, session: BackgroundSession, *, event_type: str | None = None) -> None:
        if self.storage is None or session.owner_session_id is None:
            return
        output_path = self._persist_session_output(session)
        stored_process = self._stored_process_for_session(session, output_path=output_path)
        if stored_process is None:
            return
        asyncio.create_task(self._persist_stored_process(stored_process, event_type=event_type))

    async def mark_lost_persisted_sessions(self) -> int:
        """Mark persisted running sessions as lost after a runtime restart."""
        if self.storage is None:
            return 0
        now = time.time()
        running_processes = await self.storage.list_background_processes(states=("running",))
        marked = 0
        for process in running_processes:
            metadata = dict(process.metadata or {})
            metadata.update(
                {
                    "recovery_reason": "runtime_restart",
                    "reattach_supported": False,
                    "reattach_reason": "stdout_stderr_and_watch_state_are_runtime_local",
                    "lost_policy": "mark_running_processes_lost_on_startup",
                }
            )
            updated = replace(
                process,
                state="lost",
                termination_reason="runtime_restart",
                updated_at=now,
                finished_at=now,
                metadata=metadata,
            )
            stored = await self._persist_stored_process(updated, event_type="background_process.lost")
            if stored is not None:
                marked += 1
        if marked:
            logger.info("background.process.recovered-lost | count={}", marked)
        return marked

    @staticmethod
    def _session_owned_by(
        session: BackgroundSession,
        *,
        session_id: str,
        run_id: str | None = None,
    ) -> bool:
        if session.owner_session_id != session_id:
            return False
        if run_id is not None and session.owner_run_id != run_id:
            return False
        return True

    @staticmethod
    def _session_output_text(session: BackgroundSession) -> str:
        return format_captured_output(
            session.output_chunks,
            max_chars=None,
            empty_placeholder="",
        )

    @classmethod
    def _should_notify_on_exit(cls, session: BackgroundSession) -> bool:
        if session.suppress_exit_notification or session.exit_notifier is None:
            return False
        if not session.notify_on_exit:
            return False
        if session.termination_reason == "exit" and session.exit_code == 0:
            if not cls._session_output_text(session):
                return session.notify_on_exit_empty_success
        return True

    async def _watch_session(self, session: BackgroundSession) -> None:
        try:
            if session.timeout_seconds is None:
                await session.process.wait()
            else:
                await asyncio.wait_for(session.process.wait(), timeout=session.timeout_seconds)
            if session.termination_reason is None:
                session.termination_reason = "exit"
        except asyncio.TimeoutError:
            if session.termination_reason is None:
                session.termination_reason = "timeout"
            await terminate_process_tree(session.process, wait_timeout=session.drain_timeout)
        except asyncio.CancelledError:
            if session.termination_reason is None:
                session.termination_reason = "cancelled"
            await terminate_process_tree(session.process, wait_timeout=session.drain_timeout)
            raise
        except Exception as exc:
            session.error = str(exc)
            if session.termination_reason is None:
                session.termination_reason = "error"
            await terminate_process_tree(session.process, wait_timeout=session.drain_timeout)
        finally:
            session.output_drained = await drain_process_output(
                session.read_tasks,
                timeout=session.drain_timeout,
            )
            session.exit_code = session.process.returncode
            session.state = "exited"
            session.finished_at = time.monotonic()
            session.finished_at_wall = time.time()
            self._prune_exited_sessions()
            await self._persist_session(session, event_type="background_process.completed")
            if self._should_notify_on_exit(session):
                try:
                    await session.exit_notifier(session)
                    await self._add_session_run_event(
                        session,
                        "background_process.notification_sent",
                        {"status": "sent"},
                    )
                except Exception:
                    logger.exception(
                        "background.process.notify-failed | session_id={} reason={}",
                        session.session_id,
                        session.termination_reason or "unknown",
                    )
                    await self._add_session_run_event(
                        session,
                        "background_process.notification_failed",
                        {"status": "failed"},
                    )

    async def _settle_session(self, session: BackgroundSession) -> BackgroundSession:
        watch_task = session.watch_task
        if watch_task is not None and (watch_task.done() or session.process.returncode is not None):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await watch_task
        return session

    async def list_sessions(self) -> list[BackgroundSession]:
        sessions = sorted(self._sessions.values(), key=lambda session: session.started_at)
        for session in sessions:
            await self._settle_session(session)
        return sessions

    async def list_owned_sessions(
        self,
        session_id: str,
        *,
        run_id: str | None = None,
    ) -> list[BackgroundSession]:
        sessions = await self.list_sessions()
        return [
            session
            for session in sessions
            if self._session_owned_by(session, session_id=session_id, run_id=run_id)
        ]

    async def get_session(self, session_id: str) -> BackgroundSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return await self._settle_session(session)

    async def poll_session(self, session_id: str) -> tuple[BackgroundSession, str] | None:
        session = await self.get_session(session_id)
        if session is None:
            return None

        full_output = format_captured_output(
            session.output_chunks,
            max_chars=None,
            empty_placeholder="",
        )
        if session.last_polled_chars > len(full_output):
            session.last_polled_chars = 0

        new_output = full_output[session.last_polled_chars :]
        session.last_polled_chars = len(full_output)

        if not full_output and session.last_polled_chars == 0:
            new_output = "(no output)"
        elif not new_output:
            new_output = "(no new output)"

        await self._persist_session(session)
        return session, new_output

    async def kill_session(self, session_id: str) -> BackgroundSession | None:
        session = await self.get_session(session_id)
        if session is None:
            return None

        if session.state == "running":
            if session.termination_reason is None:
                session.termination_reason = "killed"
            session.suppress_exit_notification = True
            await terminate_process_tree(session.process, wait_timeout=session.drain_timeout)
            if session.watch_task is not None:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await session.watch_task

        return session

    async def kill_owned_sessions(
        self,
        session_id: str,
        *,
        run_id: str | None = None,
    ) -> list[BackgroundSession]:
        killed: list[BackgroundSession] = []
        for session in await self.list_owned_sessions(session_id, run_id=run_id):
            if session.state != "running":
                continue
            killed_session = await self.kill_session(session.session_id)
            if killed_session is not None:
                killed.append(killed_session)
        return killed

    async def clear_session(self, session_id: str) -> BackgroundSession | None:
        session = await self.get_session(session_id)
        if session is None or session.state != "exited":
            return None

        self._sessions.pop(session.session_id, None)
        return session

    async def clear_exited_sessions(self) -> int:
        sessions = await self.list_sessions()
        exited_ids = [session.session_id for session in sessions if session.state == "exited"]
        for session_id in exited_ids:
            self._sessions.pop(session_id, None)
        return len(exited_ids)

    async def close(self) -> None:
        """Terminate all managed background sessions and drain their watcher tasks."""
        sessions = list(self._sessions.values())
        for session in sessions:
            session.suppress_exit_notification = True
            if session.state == "running":
                if session.termination_reason is None:
                    session.termination_reason = "shutdown"
                await terminate_process_tree(session.process, wait_timeout=session.drain_timeout)
            if session.watch_task is not None:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await session.watch_task

    @staticmethod
    def render_output(
        session: BackgroundSession,
        *,
        max_chars: int | None = 3000,
        empty_placeholder: str = "(no output)",
    ) -> str:
        return format_captured_output(
            session.output_chunks,
            max_chars=max_chars,
            empty_placeholder=empty_placeholder,
        )
