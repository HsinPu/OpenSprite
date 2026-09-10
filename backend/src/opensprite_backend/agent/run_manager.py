"""In-process ownership for background Agent tasks and user cancellation."""

from __future__ import annotations

import asyncio
import logging

from opensprite_backend.conversations.models import (
    RunSnapshot,
    RunStatus,
    StoreFailure,
)
from opensprite_backend.conversations.repository import (
    ConversationRepository,
    ConversationStoreError,
)
from opensprite_backend.workspaces import WorkspaceExecutionContext
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.skills.models import SkillExecutionSnapshot

from .loop import AgentLoop
from .events import INTERNAL_ERROR

_LOGGER = logging.getLogger("opensprite.agent.run_manager")


from opensprite_backend.custom_agents.models import AgentExecutionSnapshot


class RunManager:
    def __init__(
        self,
        repository: ConversationRepository,
        loop: AgentLoop,
    ) -> None:
        self._repository = repository
        self._loop = loop
        self._tasks: dict[str, asyncio.Task[RunSnapshot]] = {}
        self._cancellations: dict[str, asyncio.Event] = {}
        self._provider_references: dict[str, frozenset[str]] = {}
        self._closed = False
        self._lock = asyncio.Lock()

    async def start(
        self,
        run_id: str,
        workspace: WorkspaceExecutionContext,
        skills: SkillExecutionSnapshot | None = None,
        agents: AgentExecutionSnapshot | None = None,
        provider_endpoint: ProviderEndpointSnapshot | None = None,
    ) -> bool:
        async with self._lock:
            if self._closed:
                raise RuntimeError("run manager is closed")
            existing = self._tasks.get(run_id)
            if existing is not None and not existing.done():
                return False
            run = await asyncio.to_thread(self._repository.get_run, run_id)
            if run is None:
                raise ConversationStoreError(StoreFailure.NOT_FOUND)
            if run.status is not RunStatus.QUEUED:
                return False
            cancellation = asyncio.Event()
            task = asyncio.create_task(
                self._execute(run_id, cancellation, workspace, skills, agents, provider_endpoint),
                name=f"opensprite-run-{run_id}",
            )
            self._tasks[run_id] = task
            self._cancellations[run_id] = cancellation
            self._provider_references[run_id] = frozenset((
                run.provider_id,
                *(endpoint.provider_id for endpoint in agents.provider_endpoints),
            )) if agents is not None else frozenset((run.provider_id,))
            task.add_done_callback(
                lambda completed, owned_run_id=run_id: self._discard(
                    owned_run_id,
                    completed,
                )
            )
            return True

    def provider_in_use(self, provider_id: str) -> bool:
        """Include possible child providers retained by each live parent snapshot.

        Called on the event-loop thread under the application mutation gate.
        Terminal task callbacks release these references, not mutable Agent files.
        """
        return any(
            provider_id in references and not self._tasks[run_id].done()
            for run_id, references in self._provider_references.items()
        )

    async def _execute(
        self,
        run_id: str,
        cancellation: asyncio.Event,
        workspace: WorkspaceExecutionContext,
        skills: SkillExecutionSnapshot | None = None,
        agents: AgentExecutionSnapshot | None = None,
        provider_endpoint: ProviderEndpointSnapshot | None = None,
    ) -> RunSnapshot:
        try:
            if provider_endpoint is not None:
                return await self._loop.execute(run_id, cancellation, workspace, skills, agents, provider_endpoint)
            if agents is not None:
                return await self._loop.execute(run_id, cancellation, workspace, skills, agents)
            if skills is None:
                return await self._loop.execute(run_id, cancellation, workspace)
            return await self._loop.execute(run_id, cancellation, workspace, skills)
        except ConversationStoreError as execution_error:
            _LOGGER.exception("run execution failed run_id=%s", run_id)
            try:
                return await asyncio.to_thread(
                    self._repository.fail_run,
                    run_id,
                    INTERNAL_ERROR,
                )
            except ConversationStoreError:
                raise execution_error

    async def cancel(self, run_id: str) -> RunSnapshot:
        async with self._lock:
            cancellation = self._cancellations.get(run_id)
            result = await asyncio.to_thread(
                self._repository.request_cancel,
                run_id,
            )
            if cancellation is not None:
                cancellation.set()
            return result

    async def wait(self, run_id: str) -> RunSnapshot | None:
        async with self._lock:
            task = self._tasks.get(run_id)
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
        return await asyncio.to_thread(self._repository.get_run, run_id)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            tasks = tuple(self._tasks.values())
            for task in tasks:
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.to_thread(self._repository.interrupt_incomplete_runs)
        self._tasks.clear()
        self._cancellations.clear()
        self._provider_references.clear()

    def _discard(
        self,
        run_id: str,
        task: asyncio.Task[RunSnapshot],
    ) -> None:
        if self._tasks.get(run_id) is task:
            self._tasks.pop(run_id, None)
            self._cancellations.pop(run_id, None)
            self._provider_references.pop(run_id, None)
        if not task.cancelled():
            task.exception()
