"""Core Run lifecycle and context services for replaceable Agent drivers."""

from __future__ import annotations

import asyncio
import json
import logging
from opensprite_backend.response_modes import resolve_response_mode
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.skills.models import SkillExecutionSnapshot
from opensprite_backend.skills.execution import SkillRunState, LoadSkillTool, DiscoverSkillsTool
from datetime import UTC, datetime
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final, TypeVar
from uuid import uuid4

from opensprite_backend.conversations.models import (
    CompletionReason,
    ConversationCompaction,
    MAX_ASSISTANT_CHARS,
    Message,
    PublicRunError,
    RunEventType,
    RunSnapshot,
    RunStatus,
    StoreFailure,
)
from opensprite_backend.conversations.repository import (
    ConversationRepository,
    ConversationStoreError,
)
from opensprite_backend.inference.gateway import ModelGateway, ModelGatewayError
from opensprite_backend.inference.models import (
    InferenceFailure,
    ModelCompleted,
    ModelFinishReason,
    ModelMessage,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)
from opensprite_backend.tools.availability import (
    ToolAvailabilityProvider,
    ToolAvailabilitySnapshot,
)
from opensprite_backend.tools.dynamic import DynamicToolProvider
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.workspaces import (
    DEFAULT_WORKSPACE_ID,
    DefaultWorkspaceResolver,
    WorkspaceExecutionContext,
)

from .events import (
    AGENT_LIMIT_ERROR,
    CONTEXT_LIMIT_ERROR,
    CONTEXT_PREPARATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PROVIDER_RESPONSE,
    SCHEDULED_TOOL_APPROVAL_REQUIRED,
    WORKSPACE_CONTEXT_ERROR,
    inference_error,
)
from .context import (
    ConservativeTokenCounter,
    ContextAssembler,
    ContextBudgetPlan,
    ContextLimitExceeded,
    ConversationCompactionService,
    GatewaySummaryGenerator,
    ModelCapabilityNotFound,
    ModelCapabilityProviderError,
    ModelCapabilityResolver,
    prepare_compaction_source,
    resolve_context_budget,
)
from .prompt import StaticSystemPromptProvider, SystemPromptProvider
from ..prompt_logging import PromptLogError, PromptLogWriter
from .request_trace import Attempt, TracedGateway
from .context.receipt import ReceiptSources


from .driver import AgentDriverFactory, DriverResult
from .execution_host import LoopExecutionHost, _ExecutionFailed
from .standard_driver import StandardDriverFactory
from .strategies import ContextRetryState, ExecutionStrategy, StandardExecutionStrategy

if TYPE_CHECKING:
    from .plugin_catalog import ExecutionPluginSelection


class _RunCancelled(Exception):
    pass


class _ContextPreparationFailed(Exception):
    pass


_Result = TypeVar("_Result")
_LOGGER = logging.getLogger("opensprite.agent.context")
_MAX_UNLIMITED_CONTINUATIONS = 64
_BOUNDED_CONTINUATIONS = {
    "1": 1,
    "2": 2,
    "3": 3,
    "5": 5,
    "10": 10,
    "20": 20,
    "50": 50,
}
_CONTINUATION_TAIL_TOKENS = 4_096
_CONTEXT_PAGE_SIZE: Final = 200
_ASSISTANT_DELTA_BATCH_CHARS: Final = 4_096
_CONTINUATION_INSTRUCTION = (
    "Continue the assistant response from the exact point where it stopped. "
    "Do not repeat or summarize text that was already produced. Do not call "
    "tools. Return only the continuation of the response."
)


@dataclass(frozen=True, slots=True)
class _PreparedContext:
    messages: tuple[ModelMessage, ...]
    tools: tuple[ModelToolDefinition, ...]
    budget: ContextBudgetPlan
    compaction_id: str | None = None
    sources: ReceiptSources = ReceiptSources()


class _AssistantDeltaBuffer:
    """Coalesce fast model chunks before persisting them to SQLite."""

    def __init__(
        self,
        repository: ConversationRepository,
        run_id: str,
        *,
        batch_chars: int = _ASSISTANT_DELTA_BATCH_CHARS,
    ) -> None:
        self._repository = repository
        self._run_id = run_id
        self._batch_chars = batch_chars
        self._pending: list[str] = []
        self._pending_chars = 0

    async def append(self, text: str) -> None:
        self._pending.append(text)
        self._pending_chars += len(text)
        if self._pending_chars >= self._batch_chars:
            await self.flush()

    async def flush(self) -> None:
        if not self._pending:
            return
        text = "".join(self._pending)
        await asyncio.to_thread(
            self._repository.append_assistant_delta,
            self._run_id,
            text,
        )
        self._pending.clear()
        self._pending_chars = 0


from opensprite_backend.custom_agents.models import AgentExecutionSnapshot, AgentError
from opensprite_backend.custom_agents.delegation import DelegationCoordinator, ParentDelegation
from opensprite_backend.custom_agents.delegation_tools import delegation_tools, DELEGATION_NAMES
from opensprite_backend.custom_agents.discovery import discovery_prompt


class AgentLoop:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        gateway: ModelGateway,
        tools: ToolRegistry,
        tool_availability: ToolAvailabilityProvider | None = None,
        dynamic_tools: DynamicToolProvider | None = None,
        capability_resolver: ModelCapabilityResolver,
        system_prompt_provider: SystemPromptProvider | None = None,
        max_model_rounds: int = 8,
        max_tool_calls: int = 16,
        max_compactions_per_run: int | None = None,
        max_assistant_chars: int = MAX_ASSISTANT_CHARS,
        prompt_log_writer: PromptLogWriter | None = None,
        allow_tool_approval: bool = True,
        delegation: DelegationCoordinator | None = None,
        driver_factory: AgentDriverFactory | None = None,
        execution_strategy: ExecutionStrategy | None = None,
    ) -> None:
        if not 1 <= max_model_rounds <= 32:
            raise ValueError("invalid model round bound")
        if not 0 <= max_tool_calls <= 64:
            raise ValueError("invalid tool call bound")
        if max_compactions_per_run is not None and not 1 <= max_compactions_per_run <= 32:
            raise ValueError("invalid compaction bound")
        if not 1 <= max_assistant_chars <= MAX_ASSISTANT_CHARS:
            raise ValueError("invalid assistant output bound")
        self._repository = repository
        self._gateway = TracedGateway(gateway, repository)
        self._tools = tools
        self._tool_availability = tool_availability
        self._dynamic_tools = dynamic_tools
        self._capability_resolver = capability_resolver
        self._counter = ConservativeTokenCounter()
        self._context_assembler = ContextAssembler(self._counter)
        self._compaction_service = ConversationCompactionService(
            repository,
            GatewaySummaryGenerator(self._gateway),
        )
        self._system_prompt_provider = (
            system_prompt_provider
            if system_prompt_provider is not None
            else StaticSystemPromptProvider()
        )
        self._max_model_rounds = max_model_rounds
        self._max_tool_calls = max_tool_calls
        self._max_compactions_per_run = max_compactions_per_run
        self._max_assistant_chars = max_assistant_chars
        self._prompt_log_writer = prompt_log_writer
        self._allow_tool_approval = allow_tool_approval
        self._delegation = delegation
        self._driver_factory = driver_factory if driver_factory is not None else StandardDriverFactory()
        self._execution_strategy = (
            execution_strategy if execution_strategy is not None else StandardExecutionStrategy()
        )

    async def execute(
        self, run_id: str, cancellation_event: asyncio.Event,
        workspace: WorkspaceExecutionContext | None = None,
        skills: SkillExecutionSnapshot | None = None,
        agents: AgentExecutionSnapshot | None = None,
        provider_endpoint: ProviderEndpointSnapshot | None = None,
        *, execution_plugins: ExecutionPluginSelection | None = None,
    ) -> RunSnapshot:
        try:
            return await self._execute(run_id, cancellation_event, workspace, skills, agents, provider_endpoint,
                                       execution_plugins=execution_plugins)
        finally:
            if self._delegation is not None:
                cleanup = asyncio.create_task(self._delegation.release(run_id))
                cleanup_cancelled = False
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        cleanup_cancelled = True
                        continue
                cleanup.result()
                if cleanup_cancelled:
                    raise asyncio.CancelledError

    async def _execute(
        self,
        run_id: str,
        cancellation_event: asyncio.Event,
        workspace: WorkspaceExecutionContext | None = None,
        skills: SkillExecutionSnapshot | None = None,
        agents: AgentExecutionSnapshot | None = None,
        provider_endpoint: ProviderEndpointSnapshot | None = None,
        *, execution_plugins: ExecutionPluginSelection | None = None,
    ) -> RunSnapshot:
        run = await asyncio.to_thread(self._repository.get_run, run_id)
        if run is None:
            raise ConversationStoreError(StoreFailure.NOT_FOUND)
        if run.status is not RunStatus.QUEUED:
            return run
        if cancellation_event.is_set():
            return await asyncio.to_thread(self._repository.request_cancel, run_id)
        if workspace is None:
            if run.workspace_id != DEFAULT_WORKSPACE_ID:
                return await self._fail(run_id, WORKSPACE_CONTEXT_ERROR)
            workspace = DefaultWorkspaceResolver().execution_context(run.workspace_id)
        delta_buffer = _AssistantDeltaBuffer(self._repository, run_id)
        try:
            driver_factory = execution_plugins.driver_factory if execution_plugins else self._driver_factory
            try:
                execution_strategy = execution_plugins.make_strategy() if execution_plugins else self._execution_strategy
            except Exception:
                raise _ExecutionFailed(INTERNAL_ERROR) from None
            if (
                workspace.id != run.workspace_id
                or workspace.revision != run.workspace_revision
                or workspace.name != run.workspace_name_snapshot
                or workspace.root_hash != run.workspace_root_hash
                or workspace.mount_manifest_hash != run.workspace_mount_manifest_hash
            ):
                return await self._fail(run_id, WORKSPACE_CONTEXT_ERROR)
            run = await asyncio.to_thread(
                self._repository.mark_run_started,
                run_id,
                workspace.availability,
                tuple(
                    {
                        "id": mount.id,
                        "alias": mount.alias,
                        "rootHash": mount.root_hash,
                        "accessMode": mount.access_mode.value,
                        "enabled": mount.enabled,
                        "availability": mount.availability.value,
                    }
                    for mount in workspace.mounts
                ),
            )
            if execution_plugins is not None:
                await asyncio.to_thread(self._repository.append_run_event, run_id,
                                        RunEventType.EXECUTION_SELECTED, execution_plugins.profile())
            run_tools = (
                self._tools.extended(await self._dynamic_tools.snapshot_tools())
                if self._dynamic_tools is not None
                else self._tools
            )
            availability = (
                await self._tool_availability.snapshot()
                if self._tool_availability is not None
                else ToolAvailabilitySnapshot(
                    frozenset(
                        definition.name for definition in run_tools.definitions()
                    )
                )
            )
            system_prompt = await self._system_prompt_provider.build(
                run_id=run_id,
                workspace=workspace,
            )
            capability = await self._await_with_cancellation(
                self._resolve_run_capability(run, provider_endpoint), cancellation_event)
            if run.reasoning_resolution is None:
                run = await asyncio.to_thread(self._repository.set_reasoning_resolution, run.id, resolve_response_mode(run.response_mode, capability.reasoning_efforts))
            if not capability.supports_tools:
                availability = ToolAvailabilitySnapshot(frozenset())
                system_prompt += "\nTool calling is disabled for this model. No tools are available. Do not simulate tool calls with JSON text. Explain this limitation if a tool is requested."
            if self._delegation is not None and agents is not None and agents.available:
                capability = await self._await_with_cancellation(
                    self._resolve_run_capability(run, provider_endpoint), cancellation_event)
                if capability.supports_tools:
                    self._delegation.register(ParentDelegation(
                        run, workspace, skills or SkillExecutionSnapshot(), agents,
                        run_tools, availability, system_prompt, execution_plugins=execution_plugins))
                    run_tools = run_tools.extended(delegation_tools())
                    availability = ToolAvailabilitySnapshot(availability.enabled_names | DELEGATION_NAMES)
                    system_prompt += discovery_prompt(agents)
            skill_state = SkillRunState(skills or SkillExecutionSnapshot())
            base_system_prompt = system_prompt
            system_prompt = skill_state.prompt(base_system_prompt)
            if skill_state.snapshot.available:
                capability = await self._await_with_cancellation(self._resolve_run_capability(run, provider_endpoint), cancellation_event)
                if capability.supports_tools:
                    run_tools = run_tools.extended((LoadSkillTool(), DiscoverSkillsTool()))
                    availability = ToolAvailabilitySnapshot(availability.enabled_names | {"load_skill", "discover_skills"})
                else:
                    system_prompt += "\nAutomatic Skill selection is unavailable for this model. Only manually selected Skills are loaded."
            prepared = await self._prepare_context(
                run=run,
                provider_endpoint=provider_endpoint,
                system_prompt=system_prompt,
                cancellation_event=cancellation_event,
                availability=availability,
                tools=run_tools,
                current_user_message_id=run.user_message_id,
            )
            for identifier in skill_state.loaded:
                await asyncio.to_thread(self._repository.append_run_event, run_id, RunEventType.SKILL_LOADED,
                                        skill_state.event(identifier, "manual"))
            host = LoopExecutionHost(
                loop=self, run=run, cancellation_event=cancellation_event, workspace=workspace,
                tools=run_tools, availability=availability, prepared=prepared,
                system_prompt=system_prompt, base_system_prompt=base_system_prompt,
                skill_state=skill_state, delta_buffer=delta_buffer, strategy=execution_strategy,
                provider_endpoint=provider_endpoint,
            )
            try:
                try:
                    driver = driver_factory.create()
                except Exception:
                    raise _ExecutionFailed(INTERNAL_ERROR) from None
                try:
                    result = await self._await_with_cancellation(driver.execute(host), cancellation_event)
                except Exception as error:
                    raise self._driver_exception(error, host, cancellation_event) from None
                try:
                    await host._validate_result(result)
                except Exception as error:
                    raise self._driver_exception(error, host, cancellation_event) from None
                await delta_buffer.flush()
                self._raise_if_cancelled(cancellation_event)
                try:
                    completed = await asyncio.to_thread(
                        self._repository.complete_run, run_id, result.text, result.completion_reason)
                    return completed.run
                except ConversationStoreError as error:
                    if error.failure is StoreFailure.INVALID_STATE:
                        # request_cancel can win the SQLite transaction after
                        # the last event check. Its persisted status, rather
                        # than an arbitrary store error, proves that Stop won.
                        current = await asyncio.to_thread(self._repository.get_run, run_id)
                        if current is not None and current.status is RunStatus.CANCELLING:
                            return await self._cancel(run_id)
                        if current is not None and current.status is RunStatus.CANCELLED:
                            return current
                    raise
            finally:
                await host._close()
        except _ExecutionFailed as error:
            await delta_buffer.flush()
            return await self._fail(run_id, error.error)
        except _RunCancelled:
            await delta_buffer.flush()
            return await self._cancel(run_id)
        except ModelGatewayError as error:
            await delta_buffer.flush()
            return await self._fail(run_id, inference_error(error.failure))
        except ContextLimitExceeded:
            await delta_buffer.flush()
            return await self._fail(run_id, CONTEXT_LIMIT_ERROR)
        except ModelCapabilityNotFound:
            await delta_buffer.flush()
            return await self._fail(run_id, CONTEXT_PREPARATION_ERROR)
        except _ContextPreparationFailed:
            await delta_buffer.flush()
            return await self._fail(run_id, CONTEXT_PREPARATION_ERROR)
        except ModelCapabilityProviderError as error:
            await delta_buffer.flush()
            return await self._fail(run_id, inference_error(error.failure))
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                # Preserve RunManager.close and owner-task timeout semantics.
                raise
            # A plugin's own CancelledError does not cancel the owning Run
            # task. Persist a terminal result before RunManager releases it.
            await delta_buffer.flush()
            if cancellation_event.is_set():
                return await self._cancel(run_id)
            return await self._fail(run_id, INTERNAL_ERROR)
        except ConversationStoreError:
            raise
        except Exception:
            await delta_buffer.flush()
            _LOGGER.exception("agent run failed run_id=%s", run_id)
            return await self._fail(run_id, INTERNAL_ERROR)

    @staticmethod
    def _driver_exception(
        error: Exception, host: LoopExecutionHost, cancellation_event: asyncio.Event,
    ) -> Exception:
        # Cancellation can interrupt driver cleanup, which may itself raise.
        # The accepted Run's actual cancellation request still takes precedence.
        if cancellation_event.is_set():
            return _RunCancelled()
        if host._owns_exception(error) and isinstance(error, (
            _ExecutionFailed, ModelGatewayError, ContextLimitExceeded,
            ModelCapabilityNotFound, _ContextPreparationFailed,
            ModelCapabilityProviderError, ConversationStoreError,
        )):
            return error
        # Plugins can import core exception classes. A matching type grants no
        # authority to persist its payload or log its traceback.
        return _ExecutionFailed(INTERNAL_ERROR)

    async def _continue_output(
        self,
        *,
        run: RunSnapshot,
        system_prompt: str,
        base_transcript: tuple[ModelMessage, ...],
        prepared: _PreparedContext,
        accumulated_text: str,
        cancellation_event: asyncio.Event,
        availability: ToolAvailabilitySnapshot,
        tools: ToolRegistry,
        prompt_log_sequence: list[int],
        delta_buffer: _AssistantDeltaBuffer,
        receipt_skills: tuple[dict[str, object], ...] = (),
        provider_endpoint: ProviderEndpointSnapshot | None = None,
        execution_strategy: ExecutionStrategy,
    ) -> DriverResult:
        continuation_base = base_transcript
        configured_max = (
            None
            if run.output_continuation == "unlimited"
            else _BOUNDED_CONTINUATIONS[run.output_continuation]
        )
        attempt_limit = configured_max or _MAX_UNLIMITED_CONTINUATIONS
        for attempt in range(1, attempt_limit + 1):
            request_id = str(uuid4())
            previous_attempt: Attempt | None = None
            self._raise_if_cancelled(cancellation_event)
            await asyncio.to_thread(
                self._repository.append_run_event,
                run.id,
                RunEventType.RESPONSE_CONTINUATION_STARTED,
                {"attempt": attempt, "maxAttempts": configured_max},
            )
            context_retry_used = False
            while True:
                try:
                    transcript = self._continuation_transcript(
                        continuation_base,
                        accumulated_text,
                        prepared.budget,
                    )
                except ContextLimitExceeded:
                    if context_retry_used or not execution_strategy.allow_context_retry(
                        ContextRetryState("continuation", "local_budget")):
                        return await self._complete_partial(
                            run.id,
                            accumulated_text,
                            CompletionReason.CONTEXT_LIMIT,
                            cancellation_event,
                        )
                    context_retry_used = True
                    try:
                        prepared = await self._prepare_context(
                            run=run,
                            provider_endpoint=provider_endpoint,
                            system_prompt=system_prompt,
                            cancellation_event=cancellation_event,
                            availability=availability,
                            tools=tools,
                            force_compaction=True,
                            compaction_limit=1,
                            compaction_reason="local_budget",
                            current_user_message_id=run.user_message_id,
                        )
                    except ContextLimitExceeded:
                        return await self._complete_partial(
                            run.id,
                            accumulated_text,
                            CompletionReason.CONTEXT_LIMIT,
                            cancellation_event,
                        )
                    continuation_base = prepared.messages
                    continue

                estimated_round_tokens = self._counter.request(transcript, ())
                await asyncio.to_thread(
                    self._repository.append_run_event,
                    run.id,
                    RunEventType.MODEL_STARTED,
                    self._model_started_event_data(
                        run=run,
                        budget=prepared.budget,
                        context_tokens=estimated_round_tokens,
                        tool_definitions=(),
                    ),
                )
                request = ModelRequest(
                    provider_id=run.provider_id,
                    provider_endpoint=provider_endpoint,
                    model_id=run.model_id,
                    response_mode=run.response_mode,
                    reasoning_resolution=run.reasoning_resolution,
                    messages=transcript,
                    tools=(),
                    max_output_tokens=prepared.budget.output_reserve_tokens,
                )
                self._write_prompt_log(
                    run=run,
                    request=request,
                    request_kind=f"continuation-{attempt:02d}",
                    sequence=prompt_log_sequence,
                )
                round_text = ""
                completion: ModelCompleted | None = None
                events = self._with_cancellation(
                    self._gateway.stream(request, attempt=(current_attempt := Attempt(
                        run.id, request_id, "continuation",
                        number=1 if previous_attempt is None else previous_attempt.number + 1,
                        retry_of=None if previous_attempt is None else previous_attempt.id,
                        cause=None if previous_attempt is None else "provider_context_limit",
                        compaction_id=prepared.compaction_id,
                        sources=replace(prepared.sources, skills=receipt_skills),
                    ))),
                    cancellation_event,
                )
                retry_with_compaction = False
                while True:
                    try:
                        event = await anext(events)
                    except StopAsyncIteration:
                        break
                    except ModelGatewayError as error:
                        if (
                            error.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED
                            and not round_text
                            and not context_retry_used
                            and execution_strategy.allow_context_retry(
                                ContextRetryState("continuation", "provider_context_limit"))
                        ):
                            context_retry_used = True
                            previous_attempt = current_attempt
                            try:
                                prepared = await self._prepare_context(
                                    run=run,
                                    provider_endpoint=provider_endpoint,
                                    system_prompt=system_prompt,
                                    cancellation_event=cancellation_event,
                                    availability=availability,
                                    tools=tools,
                                    force_compaction=True,
                                    compaction_limit=1,
                                    current_user_message_id=run.user_message_id,
                                    parent_request_id=request_id,
                                )
                            except ContextLimitExceeded:
                                return await self._complete_partial(
                                    run.id,
                                    accumulated_text,
                                    CompletionReason.CONTEXT_LIMIT,
                                    cancellation_event,
                                )
                            continuation_base = prepared.messages
                            retry_with_compaction = True
                            break
                        if error.failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED:
                            return await self._complete_partial(
                                run.id,
                                accumulated_text,
                                CompletionReason.CONTEXT_LIMIT,
                                cancellation_event,
                            )
                        raise
                    if completion is not None:
                        await delta_buffer.flush()
                        raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                    if isinstance(event, ModelTextDelta):
                        if not event.text or len(event.text) > 16384:
                            await delta_buffer.flush()
                            raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE,)
                        if len(accumulated_text) + len(event.text) > self._max_assistant_chars:
                            await delta_buffer.flush()
                            raise _ExecutionFailed(AGENT_LIMIT_ERROR)
                        round_text += event.text
                        accumulated_text += event.text
                        await delta_buffer.append(event.text)
                    elif isinstance(event, ModelCompleted):
                        completion = event
                    elif isinstance(event, ModelUsage):
                        _LOGGER.info(
                            "model continuation usage run_id=%s attempt=%s input_tokens=%s output_tokens=%s",
                            run.id,
                            attempt,
                            event.input_tokens,
                            event.output_tokens,
                        )
                    else:
                        await delta_buffer.flush()
                        raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                if retry_with_compaction:
                    continue
                if completion is None or not round_text.strip():
                    await delta_buffer.flush()
                    raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                if completion.reason is ModelFinishReason.FINAL:
                    await delta_buffer.flush()
                    return await self._complete_partial(
                        run.id,
                        accumulated_text,
                        CompletionReason.STOP,
                        cancellation_event,
                    )
                if completion.reason is not ModelFinishReason.OUTPUT_LIMIT:
                    await delta_buffer.flush()
                    raise _ExecutionFailed(INVALID_PROVIDER_RESPONSE)
                await delta_buffer.flush()
                break
        if configured_max is None:
            _LOGGER.warning(
                "unlimited continuation safety cap reached run_id=%s attempts=%s",
                run.id,
                attempt_limit,
            )
        await delta_buffer.flush()
        return await self._complete_partial(
            run.id,
            accumulated_text,
            CompletionReason.OUTPUT_LIMIT,
            cancellation_event,
        )

    async def _complete_partial(
        self,
        run_id: str,
        accumulated_text: str,
        reason: CompletionReason,
        cancellation_event: asyncio.Event,
    ) -> DriverResult:
        self._raise_if_cancelled(cancellation_event)
        if self._delegation is not None:
            await self._await_with_cancellation(self._delegation.settle(run_id), cancellation_event)
        return DriverResult(accumulated_text, reason)

    def _write_prompt_log(
        self,
        *,
        run: RunSnapshot,
        request: ModelRequest,
        request_kind: str,
        sequence: list[int],
    ) -> None:
        if not run.log_full_prompts or self._prompt_log_writer is None:
            return
        sequence[0] += 1
        try:
            self._prompt_log_writer.write(
                run_id=run.id,
                created_at=datetime.now(UTC),
                request_kind=request_kind,
                request_sequence=sequence[0],
                provider_id=request.provider_id,
                model_id=request.model_id,
                response_mode=request.response_mode,
                reasoning_effort=request.reasoning_resolution.effective if request.reasoning_resolution else None,
                max_output_tokens=request.max_output_tokens,
                messages=request.messages,
                tools=request.tools,
            )
        except PromptLogError:
            _LOGGER.warning(
                "full prompt log failed run_id=%s request_kind=%s",
                run.id,
                request_kind,
            )

    @staticmethod
    def _model_started_event_data(
        *,
        run: RunSnapshot,
        budget: ContextBudgetPlan,
        context_tokens: int,
        tool_definitions: tuple[ModelToolDefinition, ...],
    ) -> dict[str, object]:
        return {
            "providerId": run.provider_id,
            "modelId": run.model_id,
            "responseMode": run.response_mode,
            "maxOutputTokens": budget.output_reserve_tokens,
            "contextTokens": context_tokens,
            "contextLimitTokens": budget.context_limit_tokens,
            "inputBudgetTokens": budget.input_budget_tokens,
            "toolNames": [tool.name for tool in tool_definitions],
        }

    def _continuation_transcript(
        self,
        base_transcript: tuple[ModelMessage, ...],
        accumulated_text: str,
        budget: ContextBudgetPlan,
    ) -> tuple[ModelMessage, ...]:
        if not base_transcript or base_transcript[0].role != "system":
            raise ContextLimitExceeded
        instructed = (
            ModelMessage(
                role="system",
                content=f"{base_transcript[0].content}\n\n{_CONTINUATION_INSTRUCTION}",
            ),
            *base_transcript[1:],
        )
        base_tokens = self._counter.request(instructed, ())
        available = min(
            _CONTINUATION_TAIL_TOKENS,
            budget.input_budget_tokens - base_tokens - 8,
        )
        if available < 1:
            raise ContextLimitExceeded
        low = 1
        high = len(accumulated_text)
        best: str | None = None
        while low <= high:
            middle = (low + high) // 2
            candidate_text = accumulated_text[-middle:]
            candidate = ModelMessage(role="assistant", content=candidate_text)
            if self._counter.message(candidate) <= available:
                best = candidate_text
                low = middle + 1
            else:
                high = middle - 1
        if best is None:
            raise ContextLimitExceeded
        result = (*instructed, ModelMessage(role="assistant", content=best))
        if self._counter.request(result, ()) > budget.input_budget_tokens:
            raise ContextLimitExceeded
        return result

    async def _resolve_run_capability(self, run: RunSnapshot, endpoint: ProviderEndpointSnapshot | None):
        if endpoint is None:
            return await self._capability_resolver.resolve(run.provider_id, run.model_id)
        if endpoint.protocol != "openai_chat_completions":
            capability = await self._capability_resolver.resolve(run.provider_id, run.model_id)
            return replace(capability, supports_tools=capability.supports_tools and endpoint.tools_enabled and run.model_id not in endpoint.disabled_models)
        for model in endpoint.models:
            if model.provider_id == run.provider_id and model.model_id == run.model_id:
                return model
        raise ModelCapabilityNotFound

    async def _prepare_context(
        self,
        *,
        run: RunSnapshot,
        system_prompt: str,
        cancellation_event: asyncio.Event,
        availability: ToolAvailabilitySnapshot | None = None,
        tools: ToolRegistry | None = None,
        force_compaction: bool = False,
        compaction_reason: str = "provider_context_limit",
        provider_endpoint: ProviderEndpointSnapshot | None = None,
        compaction_limit: int | None = None,
        current_user_message_id: str | None = None,
        parent_request_id: str | None = None,
    ) -> _PreparedContext:
        self._raise_if_cancelled(cancellation_event)
        limit = (
            self._max_compactions_per_run
            if compaction_limit is None
            else compaction_limit
        )
        if limit is not None and not 0 <= limit <= 32:
            raise ValueError("invalid Context compaction limit")
        _LOGGER.info(
            "context preparing run_id=%s provider_id=%s model_id=%s budget=%s force_compaction=%s",
            run.id,
            run.provider_id,
            run.model_id,
            run.context_budget,
            force_compaction,
        )
        capability = await self._await_with_cancellation(
            self._resolve_run_capability(run, provider_endpoint),
            cancellation_event,
        )
        budget = resolve_context_budget(
            run.context_budget,
            capability,
            run.output_budget,
        )
        resolved_tools = tools or self._tools
        resolved_availability = availability or ToolAvailabilitySnapshot(
            frozenset(definition.name for definition in resolved_tools.definitions())
        )
        tool_definitions = tuple(
            ModelToolDefinition(
                name=definition.name,
                description=definition.description,
                input_schema=dict(definition.input_schema),
            )
            for definition in resolved_tools.definitions(resolved_availability)
        )
        page = await asyncio.to_thread(
            self._repository.list_messages,
            run.conversation_id,
            limit=_CONTEXT_PAGE_SIZE,
            before_sequence=None,
        )
        summary = await asyncio.to_thread(
            self._repository.get_latest_compaction,
            run.conversation_id,
        )

        force_compaction_pending = force_compaction
        compaction_index = 0
        last_compaction_id: str | None = None
        while True:
            coverage = 0 if summary is None else summary.covers_through_sequence
            uncovered = tuple(
                message for message in page.items if message.sequence > coverage
            )
            has_older = bool(
                page.next_before_sequence is not None
                and page.items
                and coverage < page.items[0].sequence - 1
            )
            try:
                assembled = self._context_assembler.assemble(
                    system_prompt=system_prompt,
                    history=uncovered,
                    tools=tool_definitions,
                    budget=budget,
                    summary=summary,
                    has_older_history=has_older,
                    current_user_message_id=current_user_message_id,
                )
            except ContextLimitExceeded:
                raise
            except ValueError as error:
                raise _ContextPreparationFailed from error
            if not assembled.needs_compaction and not force_compaction_pending:
                _LOGGER.info(
                    "context prepared run_id=%s context_limit=%s input_budget=%s estimated_input=%s messages=%s compacted_through=%s",
                    run.id,
                    budget.context_limit_tokens,
                    budget.input_budget_tokens,
                    assembled.estimated_input_tokens,
                    assembled.included_message_count,
                    coverage,
                )
                return _PreparedContext(
                    messages=assembled.messages,
                    tools=tool_definitions,
                    budget=budget,
                    compaction_id=last_compaction_id,
                    sources=ReceiptSources(
                        bindings=tuple(
                            (model_message, "currentUser" if message.id == current_user_message_id else "history", message.id, message.sequence)
                            for model_message, message in zip(
                                assembled.messages[-assembled.included_message_count:] if assembled.included_message_count else (),
                                uncovered[-assembled.included_message_count:] if assembled.included_message_count else (),
                            )
                        ) + (() if summary is None else ((assembled.messages[1], "summary", summary.id, summary.covers_through_sequence),)),
                        summary=None if summary is None else {"id": summary.id, "version": summary.summary_version,
                            "sourceHash": summary.source_hash, "throughSequence": summary.covers_through_sequence},
                        workspace={"id": run.workspace_id, "revision": run.workspace_revision,
                            "mountManifestHash": run.workspace_mount_manifest_hash},
                        context_limit=budget.context_limit_tokens, input_budget=budget.input_budget_tokens,
                    ),
                )
            if limit is not None and compaction_index >= limit:
                raise ContextLimitExceeded

            protected_sequence = (
                uncovered[-12].sequence
                if len(uncovered) >= 12
                else uncovered[0].sequence
                if uncovered
                else page.items[-1].sequence + 1
            )
            candidates = await asyncio.to_thread(
                self._repository.list_messages_after,
                run.conversation_id,
                after_sequence=coverage,
                limit=_CONTEXT_PAGE_SIZE,
            )
            candidates = tuple(
                message
                for message in candidates
                if message.sequence < protected_sequence
            )
            if not candidates:
                raise ContextLimitExceeded
            compaction_id = str(uuid4())
            compaction_started = False
            try:
                self._raise_if_cancelled(cancellation_event)
                candidates = self._fit_compaction_source(
                    summary,
                    candidates,
                    budget.input_budget_tokens,
                )
                await asyncio.to_thread(
                    self._repository.append_run_event,
                    run.id,
                    RunEventType.CONTEXT_COMPACTION_STARTED,
                    {
                        "schemaVersion": 1,
                        "compactionId": compaction_id,
                        "reason": compaction_reason if force_compaction_pending else "local_budget",
                        "fromSequence": candidates[0].sequence,
                        "throughSequence": candidates[-1].sequence,
                        "estimatedBeforeTokens": assembled.estimated_input_tokens,
                        "inputBudgetTokens": budget.input_budget_tokens,
                    },
                )
                compaction_started = True
                with self._gateway.scope(Attempt(run.id, str(uuid4()), "compaction", compaction_id=compaction_id, parent_request_id=parent_request_id,
                    sources=ReceiptSources(
                        history_ids=tuple(message.id for message in candidates),
                        summary=None if summary is None else {"id": summary.id, "version": summary.summary_version,
                            "sourceHash": summary.source_hash, "throughSequence": summary.covers_through_sequence},
                        workspace={"id": run.workspace_id, "revision": run.workspace_revision,
                            "mountManifestHash": run.workspace_mount_manifest_hash},
                        context_limit=budget.context_limit_tokens, input_budget=budget.input_budget_tokens,
                    ))):
                    summary = await self._await_with_cancellation(
                        self._compaction_service.compact(
                            conversation_id=run.conversation_id,
                            provider_id=run.provider_id,
                            model_id=run.model_id,
                            previous=summary,
                            messages=candidates,
                            provider_endpoint=provider_endpoint,
                        ),
                        cancellation_event,
                    )
                if summary.covers_through_sequence <= coverage:
                    raise _ContextPreparationFailed
                await asyncio.to_thread(
                    self._repository.append_run_event,
                    run.id,
                    RunEventType.CONTEXT_COMPACTION_COMPLETED,
                    {
                        "schemaVersion": 1,
                        "compactionId": compaction_id,
                        "throughSequence": summary.covers_through_sequence,
                        "inputTokens": summary.input_tokens,
                        "outputTokens": summary.output_tokens,
                    },
                )
                force_compaction_pending = False
                last_compaction_id = compaction_id
                compaction_index += 1
            except (_RunCancelled, asyncio.CancelledError):
                if compaction_started:
                    await asyncio.to_thread(
                        self._repository.append_run_event, run.id,
                        RunEventType.CONTEXT_COMPACTION_CANCELLED,
                        {"schemaVersion": 1, "compactionId": compaction_id, "reason": "cancelled"},
                    )
                raise
            except Exception as error:
                if compaction_started:
                    await asyncio.to_thread(
                        self._repository.append_run_event, run.id,
                        RunEventType.CONTEXT_COMPACTION_FAILED,
                        {
                            "schemaVersion": 1, "compactionId": compaction_id,
                            "errorCode": "context_limit" if isinstance(error, ContextLimitExceeded)
                            else "provider_failed" if isinstance(error, ModelGatewayError)
                            else "preparation_failed",
                        },
                    )
                if isinstance(error, ValueError):
                    raise _ContextPreparationFailed from error
                raise
            _LOGGER.info(
                "context compacted run_id=%s through_sequence=%s input_tokens=%s output_tokens=%s",
                run.id,
                summary.covers_through_sequence,
                summary.input_tokens,
                summary.output_tokens,
            )
        raise ContextLimitExceeded  # pragma: no cover

    def _fit_compaction_source(
        self,
        previous: ConversationCompaction | None,
        candidates: tuple[Message, ...],
        input_budget_tokens: int,
    ) -> tuple[Message, ...]:
        selected: list[Message] = []
        source_characters = 0 if previous is None else len(previous.summary)
        for candidate in candidates:
            if source_characters + len(candidate.content) > 400_000:
                break
            selected.append(candidate)
            source_characters += len(candidate.content)
        while selected:
            source = prepare_compaction_source(previous, tuple(selected))
            if (
                len(source.prompt) <= 1_000_000
                and self._counter.text(source.prompt) + 64 <= input_budget_tokens
            ):
                return tuple(selected)
            selected.pop()
        raise ContextLimitExceeded


    async def _fail(
        self,
        run_id: str,
        error: PublicRunError,
    ) -> RunSnapshot:
        if self._delegation is not None:
            await self._delegation.settle(run_id, cancel=True)
        return await asyncio.to_thread(self._repository.fail_run, run_id, error)

    async def _cancel(self, run_id: str) -> RunSnapshot:
        if self._delegation is not None:
            await self._delegation.settle(run_id, cancel=True)
        requested = await asyncio.to_thread(self._repository.request_cancel, run_id)
        if requested.status is RunStatus.CANCELLED:
            return requested
        return await asyncio.to_thread(self._repository.mark_run_cancelled, run_id)

    @staticmethod
    def _raise_if_cancelled(cancellation_event: asyncio.Event) -> None:
        if cancellation_event.is_set():
            raise _RunCancelled

    @staticmethod
    async def _with_cancellation(
        stream: AsyncIterator[ModelStreamEvent],
        cancellation_event: asyncio.Event,
    ) -> AsyncIterator[ModelStreamEvent]:
        iterator = stream.__aiter__()
        try:
            while True:
                next_event = asyncio.create_task(anext(iterator))
                cancelled = asyncio.create_task(cancellation_event.wait())
                try:
                    done, _pending = await asyncio.wait(
                        {next_event, cancelled},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                except BaseException:
                    next_event.cancel()
                    cancelled.cancel()
                    await asyncio.gather(
                        next_event,
                        cancelled,
                        return_exceptions=True,
                    )
                    raise
                if cancelled in done and cancelled.result():
                    next_event.cancel()
                    with suppress(asyncio.CancelledError, StopAsyncIteration):
                        await next_event
                    raise _RunCancelled
                cancelled.cancel()
                with suppress(asyncio.CancelledError):
                    await cancelled
                try:
                    yield next_event.result()
                except StopAsyncIteration:
                    return
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                with suppress(Exception):
                    await close()

    @staticmethod
    async def _await_with_cancellation(
        awaitable: Awaitable[_Result],
        cancellation_event: asyncio.Event,
    ) -> _Result:
        operation = asyncio.ensure_future(awaitable)
        cancelled = asyncio.create_task(cancellation_event.wait())
        try:
            done, _pending = await asyncio.wait(
                {operation, cancelled},
                return_when=asyncio.FIRST_COMPLETED,
            )
        except BaseException:
            operation.cancel()
            cancelled.cancel()
            await asyncio.gather(operation, cancelled, return_exceptions=True)
            raise
        if cancelled in done and cancelled.result():
            operation.cancel()
            with suppress(asyncio.CancelledError):
                await operation
            raise _RunCancelled
        cancelled.cancel()
        with suppress(asyncio.CancelledError):
            await cancelled
        return operation.result()

    @staticmethod
    def _tool_fingerprint(call: ModelToolCall) -> str:
        return json.dumps(
            {"name": call.name, "arguments": call.arguments},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
