"""Parent-scoped delegation with immutable inputs and owned completion watchers."""

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import logging

from opensprite_backend.conversations.models import RunSnapshot
from opensprite_backend.skills.models import SkillExecutionSnapshot
from opensprite_backend.tools.availability import ToolAvailabilitySnapshot
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.workspaces import WorkspaceExecutionContext
from .child_repository import ChildExecutionRepository
from .child_tasks import ChildTaskPool, ChildTaskError
from .discovery import discover_agents
from .models import AgentExecutionSnapshot, AgentError


_LOGGER = logging.getLogger("opensprite.custom_agents.delegation")


@dataclass(frozen=True, slots=True)
class ParentDelegation:
    run: RunSnapshot
    workspace: WorkspaceExecutionContext = field(repr=False)
    skills: SkillExecutionSnapshot = field(repr=False)
    agents: AgentExecutionSnapshot = field(repr=False)
    tools: ToolRegistry = field(repr=False)
    availability: ToolAvailabilitySnapshot
    base_system_prompt: str = field(repr=False)


class DelegationCoordinator:
    def __init__(self, store: ChildExecutionRepository, executor) -> None:
        self._store = store
        self._executor = executor
        self._parents: dict[str, ParentDelegation] = {}
        self._inputs: dict[str, tuple[object, str]] = {}
        self._watchers: dict[str, asyncio.Task] = {}
        self._child_owners: dict[str, str] = {}
        self._releasing: set[str] = set()
        self._observer_errors: dict[str, str] = {}
        self._lifecycle_lock = asyncio.Lock()
        self._closed = False
        self._pool = ChildTaskPool(self._execute)

    def register(self, context: ParentDelegation) -> None:
        if self._closed:
            raise AgentError("agent_unavailable")
        if context.run.id in self._parents:
            raise AgentError("invalid_request")
        self._parents[context.run.id] = context

    async def _execute(self, parent_id, child_id):
        context = self._parents[parent_id]
        definition, task = self._inputs[child_id]
        child = await asyncio.to_thread(self._store.get, parent_id, child_id)
        return await self._executor.execute(
            child=child, parent=context.run, workspace=context.workspace,
            skills=context.skills, definition=definition, task=task,
            tools=context.tools, availability=context.availability,
            base_system_prompt=context.base_system_prompt, cancellation_event=asyncio.Event(),
        )

    async def _observe(self, parent_id, child_id):
        try:
            result = await self._pool.wait(parent_id, child_id)
            for attempt in range(2):
                try:
                    if result.state == "timed_out":
                        await asyncio.to_thread(self._store.mark_timeout, parent_id, child_id)
                    elif result.state in {"failed", "cancelled"}:
                        await asyncio.to_thread(self._store.transition, parent_id, child_id,
                                                result.state, error_code=result.error)
                    return
                except Exception as error:
                    if attempt == 0:
                        await asyncio.sleep(0)
                        continue
                    self._observer_errors[parent_id] = self._safe_error_code(error)
                    self._log_observer_error(parent_id, child_id, error)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._observer_errors[parent_id] = self._safe_error_code(error)
            self._log_observer_error(parent_id, child_id, error)

    @staticmethod
    def _safe_error_code(error: BaseException) -> str:
        return "store_unavailable"

    @staticmethod
    def _log_observer_error(parent_id: str, child_id: str, error: BaseException) -> None:
        _LOGGER.warning(
            "child observer persistence failed parent_id=%s child_id=%s code=%s",
            parent_id,
            child_id,
            DelegationCoordinator._safe_error_code(error),
        )

    @staticmethod
    async def _create_durably(operation, **arguments):
        task = asyncio.create_task(asyncio.to_thread(operation, **arguments))
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        result = task.result()
        if cancelled:
            raise asyncio.CancelledError
        return result

    @staticmethod
    def _shape(arguments, fields):
        if type(arguments) is not dict or set(arguments) != set(fields):
            raise AgentError("invalid_request")

    async def invoke(self, parent_id: str, call_id: str, name: str, arguments: dict):
        # Only acceptance is serialized with release/close. Waiting for a child
        # must not hold this lock: its cancellation API needs to remain usable.
        if name == "spawn_agent":
            async with self._lifecycle_lock:
                return await self._invoke_locked(parent_id, call_id, name, arguments)
        return await self._invoke_locked(parent_id, call_id, name, arguments)

    async def _invoke_locked(self, parent_id: str, call_id: str, name: str, arguments: dict):
        if self._closed or parent_id in self._releasing:
            raise AgentError("agent_unavailable")
        context = self._parents.get(parent_id)
        if context is None:
            raise AgentError("agent_unavailable")
        try:
            if name == "discover_agents":
                return discover_agents(context.agents, arguments)
            if name == "spawn_agent":
                self._shape(arguments, ("agentId", "task", "background", "scope", "expectedOutput"))
                limits = {"agentId": 36, "task": 16000, "background": 16000,
                          "scope": 4000, "expectedOutput": 4000}
                if any(type(arguments[key]) is not str or len(arguments[key]) > limit
                       for key, limit in limits.items()) or not arguments["task"].strip():
                    raise AgentError("invalid_request")
                candidate = context.agents.get(arguments["agentId"])
                definition = candidate.definition
                if definition is None:
                    raise AgentError("agent_unavailable")
                payload = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
                child, replay = await self._create_durably(
                    self._store.create, parent_id=parent_id, call_id=call_id,
                    request_hash=hashlib.sha256(payload.encode()).hexdigest(),
                    agent_id=candidate.record.id, name=definition.name,
                    revision=candidate.record.revision, definition_hash=definition.content_hash,
                    provider_id=definition.provider_id or context.run.provider_id,
                    model_id=definition.model or context.run.model_id,
                )
                if not replay:
                    self._child_owners[child.id] = parent_id
                    self._inputs[child.id] = (definition, "DELEGATED_TASK_JSON\n" + payload + "\nEND_DELEGATED_TASK")
                    try:
                        await self._pool.spawn(parent_id, child.id)
                    except ChildTaskError as error:
                        self._inputs.pop(child.id, None)
                        try:
                            await asyncio.to_thread(
                                self._store.transition,
                                parent_id,
                                child.id,
                                "cancelled",
                                error_code=error.code,
                            )
                        except Exception as persistence_error:
                            self._log_observer_error(parent_id, child.id, persistence_error)
                            raise AgentError("store_unavailable") from None
                        raise AgentError(error.code) from None
                    self._watchers[child.id] = asyncio.create_task(self._observe(parent_id, child.id))
                return {"childId": child.id, "status": child.status, "replayed": replay}
            if name == "get_agent_result":
                self._shape(arguments, ("childId", "offset"))
                offset = arguments["offset"]
                if type(offset) is not int or offset < 0:
                    raise AgentError("invalid_request")
                child = await asyncio.to_thread(self._store.get, parent_id, arguments["childId"])
                page = child.result_text[offset:offset + 4000]
                return {"childId": child.id, "status": child.status, "error": child.error_code,
                        "text": page, "nextOffset": offset + len(page) if offset + len(page) < len(child.result_text) else None}
            if name == "wait_agents":
                self._shape(arguments, ("childIds",))
                ids = arguments["childIds"]
                if type(ids) is not list or not 1 <= len(ids) <= 6 or any(type(item) is not str for item in ids) or len(set(ids)) != len(ids):
                    raise AgentError("invalid_request")
                for child_id in ids:
                    self._pool.get(parent_id, child_id)
                await asyncio.gather(*(asyncio.shield(self._watchers[item]) for item in ids))
                children = [await asyncio.to_thread(self._store.get, parent_id, item) for item in ids]
                return {"items": [{"childId": child.id, "status": child.status} for child in children]}
            if name == "cancel_agent":
                self._shape(arguments, ("childId",))
                child_id = arguments["childId"]
                child = await self.cancel_child(parent_id, child_id)
                return {"childId": child.id, "status": child.status}
            raise AgentError("invalid_request")
        except ChildTaskError as error:
            raise AgentError(error.code) from None

    async def settle(self, parent_id: str, *, cancel: bool = False) -> None:
        await self._settle_locked(parent_id, cancel=cancel)

    async def _settle_locked(self, parent_id: str, *, cancel: bool = False) -> None:
        if parent_id not in self._parents:
            return
        if cancel:
            try:
                await self._pool.cancel_parent(parent_id)
            except ChildTaskError as error:
                if error.code != "pool_closed":
                    raise
        watchers = [task for child_id, task in self._watchers.items()
                    if self._child_owners.get(child_id) == parent_id]
        if watchers:
            results = await asyncio.gather(
                *(asyncio.shield(task) for task in watchers),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, Exception):
                    self._log_observer_error(parent_id, "unknown", result)
        observer_error = self._observer_errors.get(parent_id)
        if observer_error is not None and not cancel:
            raise AgentError(observer_error)
        # A spawn cancelled between the durable insert and task creation must
        # also be settled; it must never survive its owning parent.
        if cancel:
            try:
                children = await asyncio.to_thread(self._store.list, parent_id)
            except Exception as error:
                self._log_observer_error(parent_id, "unknown", error)
                return
            for child in children:
                if child.status in {"queued", "running", "cancelling"}:
                    try:
                        await asyncio.to_thread(
                            self._store.transition,
                            parent_id,
                            child.id,
                            "cancelled",
                            error_code="parent_cancelled",
                        )
                    except Exception as error:
                        self._log_observer_error(parent_id, child.id, error)

    async def close(self) -> None:
        async with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
        await self._pool.close()
        for parent_id in tuple(self._parents):
            await self.release(parent_id)

    async def cancel_child(self, parent_id: str, child_id: str):
        return await self._cancel_child_locked(parent_id, child_id)

    async def _cancel_child_locked(self, parent_id: str, child_id: str):
        child = await asyncio.to_thread(self._store.get, parent_id, child_id)
        if child.status not in {"queued", "running", "cancelling"}:
            return child
        if self._closed or parent_id not in self._parents:
            try:
                return await asyncio.to_thread(
                    self._store.transition,
                    parent_id,
                    child_id,
                    "cancelled",
                    error_code="parent_released",
                )
            except Exception:
                raise AgentError("store_unavailable") from None
        try:
            watcher = self._watchers.get(child_id)
            await self._pool.cancel(parent_id, child_id)
            if watcher is not None:
                await asyncio.shield(watcher)
        except ChildTaskError as error:
            current = await asyncio.to_thread(self._store.get, parent_id, child_id)
            if current.status not in {"queued", "running", "cancelling"}:
                return current
            raise AgentError(error.code) from None
        return await asyncio.to_thread(self._store.get, parent_id, child_id)

    async def release(self, parent_id: str) -> None:
        async with self._lifecycle_lock:
            if parent_id not in self._parents or parent_id in self._releasing:
                return
            self._releasing.add(parent_id)
        try:
            await self._settle_locked(parent_id, cancel=True)
        finally:
            await self._pool.forget_parent(parent_id)
            for child_id, owner in tuple(self._child_owners.items()):
                if owner == parent_id:
                    self._watchers.pop(child_id, None)
                    self._inputs.pop(child_id, None)
                    self._child_owners.pop(child_id, None)
            self._observer_errors.pop(parent_id, None)
            self._parents.pop(parent_id, None)
            self._releasing.discard(parent_id)
