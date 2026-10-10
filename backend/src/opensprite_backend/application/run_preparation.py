"""Product assembly of pinned execution inputs under the core's Run control."""
from __future__ import annotations

from dataclasses import dataclass

from opensprite_backend.agent.context.limits import resolve_model_limits
from opensprite_backend.agent.events import CONTEXT_PREPARATION_ERROR, WORKSPACE_CONTEXT_ERROR, inference_error
from opensprite_backend.agent.execution_errors import ExecutionFailed
from opensprite_backend.agent.execution_input import ExecutionPluginSelection, PreparedRun, StartedMount
from opensprite_backend.agent.run_executor import RunExecutor
from opensprite_backend.agent.plugin import AgentLoopPluginFactory
from opensprite_backend.agent.request_observer import ModelRequestObserver
from opensprite_backend.conversations.models import RunSnapshot
from opensprite_backend.execution_plugins.catalog import ExecutionPluginCatalog
from opensprite_backend.response_modes import resolve_response_mode
from opensprite_backend.system_prompt import StaticSystemPromptProvider, SystemPromptProvider
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.workspaces.models import DEFAULT_WORKSPACE_ID, WorkspaceExecutionContext
from opensprite_backend.workspaces.service import DefaultWorkspaceResolver
from .model_capability import ModelCapabilityNotFound, ModelCapabilityProviderError, ModelCapabilityResolver


@dataclass(frozen=True, slots=True)
class ProductRunPreparation:
    capabilities: ModelCapabilityResolver
    prompt_provider: SystemPromptProvider
    workspace: WorkspaceExecutionContext | None = None
    provider_endpoint: ProviderEndpointSnapshot | None = None
    selection: ExecutionPluginSelection | None = None
    plugin_factory: AgentLoopPluginFactory | None = None
    request_observer: ModelRequestObserver | None = None

    async def prepare(self, run: RunSnapshot) -> PreparedRun:
        workspace = self.workspace
        if workspace is None:
            if run.workspace_id != DEFAULT_WORKSPACE_ID:
                raise ExecutionFailed(WORKSPACE_CONTEXT_ERROR)
            workspace = DefaultWorkspaceResolver().execution_context(run.workspace_id)
        if (workspace.id, workspace.revision, workspace.name, workspace.root_hash, workspace.mount_manifest_hash) != (
                run.workspace_id, run.workspace_revision, run.workspace_name_snapshot,
                run.workspace_root_hash, run.workspace_mount_manifest_hash):
            raise ExecutionFailed(WORKSPACE_CONTEXT_ERROR)
        selection = self.selection
        if selection is None:
            selection = (ExecutionPluginSelection("standard", "testing", self.plugin_factory)
                         if self.plugin_factory is not None else ExecutionPluginCatalog().resolve("standard"))
        prompt = await self.prompt_provider.build(run_id=run.id, workspace=workspace, log_full_prompts=run.log_full_prompts)
        try:
            if self.provider_endpoint is not None and self.provider_endpoint.protocol == "openai_chat_completions":
                capability = next((model for model in self.provider_endpoint.models
                    if model.provider_id == run.provider_id and model.model_id == run.model_id), None)
                if capability is None:
                    raise ModelCapabilityNotFound
            else:
                capability = await self.capabilities.resolve(run.provider_id, run.model_id)
        except ModelCapabilityProviderError as error:
            raise ExecutionFailed(inference_error(error.failure)) from None
        except ModelCapabilityNotFound:
            raise ExecutionFailed(CONTEXT_PREPARATION_ERROR) from None
        return PreparedRun(
            run.id, prompt, resolve_model_limits(run.context_budget, capability, run.output_budget), selection,
            run.reasoning_resolution or resolve_response_mode(run.response_mode, capability.reasoning_efforts),
            self.provider_endpoint, workspace.availability,
            tuple(StartedMount(mount.id, mount.alias, mount.root_hash, mount.access_mode.value,
                               mount.enabled, mount.availability.value) for mount in workspace.mounts),
            self.request_observer if run.log_full_prompts else None,
        )


class ProductRunExecutor:
    """Compose product defaults; the execution core requires explicit inputs."""

    def __init__(self, *, repository, gateway, capability_resolver, system_prompt_provider=None,
                 request_observer=None, plugin_factory=None, **limits):
        self._executor = RunExecutor(repository=repository, gateway=gateway, **limits)
        self._capabilities = capability_resolver
        self._prompt_provider = system_prompt_provider if system_prompt_provider is not None else StaticSystemPromptProvider()
        self._request_observer = request_observer
        self._plugin_factory = plugin_factory

    async def execute(self, run_id, cancellation_event, workspace=None, provider_endpoint=None, *, execution_plugin=None):
        preparation = ProductRunPreparation(self._capabilities, self._prompt_provider, workspace,
            provider_endpoint, execution_plugin, self._plugin_factory, self._request_observer)
        return await self._executor.execute(run_id, cancellation_event, preparation=preparation)
