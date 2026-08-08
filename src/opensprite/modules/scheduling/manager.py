"""Runtime manager for per-session scheduling services."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable

from .service import CronService
from .types import CronJob


class CronSessionResetInProgress(RuntimeError):
    """Raised when cron access races with a session reset."""

    def __init__(self, session_id: str):
        super().__init__(f"Cron is unavailable while session '{session_id}' is being reset")
        self.session_id = session_id


class CronManager:
    """Manage per-session cron services under the workspace root."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        workspace_for_session: Callable[[str], Path],
        on_job: Callable[[str, CronJob], Awaitable[str | None]],
    ):
        self.workspace_root = Path(workspace_root)
        self._workspace_for_session = workspace_for_session
        self._on_job = on_job
        self._services: dict[str, CronService] = {}
        self._session_reset_locks: dict[str, asyncio.Lock] = {}
        self._session_reset_waiters: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def _jobs_path(self, session_id: str) -> Path:
        return Path(self._workspace_for_session(session_id)) / "cron" / "jobs.json"

    def _iter_jobs_paths(self):
        root = self.workspace_root / "sessions"
        if root.exists():
            yield from root.glob("*/*/cron/jobs.json")

    @staticmethod
    def _session_id_from_jobs_path(jobs_path: Path) -> str:
        try:
            return str(json.loads(jobs_path.read_text(encoding="utf-8")).get("sessionId", "")).strip()
        except Exception:
            return ""

    async def _build_service(self, session_id: str) -> CronService:
        async def on_job(job: CronJob) -> str | None:
            return await self._on_job(session_id, job)

        service = CronService(
            self._jobs_path(session_id),
            session_id=session_id,
            on_job=on_job,
        )
        await service.start()
        return service

    async def get_or_create_service(self, session_id: str) -> CronService:
        async with self._lock:
            if self._session_reset_waiters.get(session_id, 0) > 0:
                raise CronSessionResetInProgress(session_id)
            service = self._services.get(session_id)
            if service is not None:
                return service
            service = await self._build_service(session_id)
            self._services[session_id] = service
            return service

    async def get_all_services(self) -> dict[str, CronService]:
        """Return services for every discovered session with a cron store."""
        session_ids = {
            session_id
            for jobs_path in self._iter_jobs_paths()
            if (session_id := self._session_id_from_jobs_path(jobs_path))
        }
        for session_id in sorted(session_ids):
            try:
                await self.get_or_create_service(session_id)
            except CronSessionResetInProgress:
                continue
        async with self._lock:
            return dict(self._services)

    @asynccontextmanager
    async def quiesce_session(self, session_id: str) -> AsyncIterator[None]:
        """Block cron service creation while one session is being reset."""
        async with self._lock:
            reset_lock = self._session_reset_locks.setdefault(session_id, asyncio.Lock())
            self._session_reset_waiters[session_id] = self._session_reset_waiters.get(session_id, 0) + 1
        acquired = False
        try:
            await reset_lock.acquire()
            acquired = True
            async with self._lock:
                service = self._services.pop(session_id, None)
            if service is not None:
                await service.close()
            yield
        finally:
            if acquired:
                reset_lock.release()
            async with self._lock:
                remaining = self._session_reset_waiters.get(session_id, 1) - 1
                if remaining > 0:
                    self._session_reset_waiters[session_id] = remaining
                else:
                    self._session_reset_waiters.pop(session_id, None)
                    if not reset_lock.locked():
                        self._session_reset_locks.pop(session_id, None)

    async def start(self) -> None:
        for jobs_path in self._iter_jobs_paths():
            session_id = self._session_id_from_jobs_path(jobs_path)
            if not session_id:
                continue
            await self.get_or_create_service(session_id)

    async def stop(self) -> None:
        async with self._lock:
            services = list(self._services.values())
            self._services.clear()
        for service in services:
            await service.close()


__all__ = ["CronManager", "CronSessionResetInProgress"]
