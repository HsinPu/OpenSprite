"""Explicit Run inputs; no discovery, settings, renderer or transport adapter."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import inspect
from typing import Protocol

from opensprite_backend.conversations.models import RunSnapshot
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.response_modes import ReasoningResolution
from opensprite_backend.workspaces.models import WorkspaceAvailability
from .plugin import AgentLoopPlugin, AgentLoopPluginFactory, ModelLimits
from .request_observer import ModelRequestObserver

API_VERSION = 5


class ExecutionPluginError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ExecutionPluginSelection:
    plugin_id: str
    plugin_version: str
    factory: AgentLoopPluginFactory = field(repr=False)

    def create(self) -> AgentLoopPlugin:
        try:
            if type(getattr(self.factory, "api_version", None)) is not int or self.factory.api_version != API_VERSION:
                raise ValueError("invalid factory API")
            plugin = self.factory.create()
            if inspect.iscoroutine(plugin):
                plugin.close()
                raise ValueError("create must return a plugin synchronously")
            if not inspect.iscoroutinefunction(getattr(plugin, "execute", None)):
                raise ValueError("execute must be async")
            return plugin
        except (Exception, asyncio.CancelledError):
            raise ExecutionPluginError("plugin_unavailable") from None

    def profile(self) -> dict[str, object]:
        return {"pluginId": self.plugin_id, "pluginVersion": self.plugin_version, "apiVersion": API_VERSION}


@dataclass(frozen=True, slots=True)
class StartedMount:
    id: str
    alias: str
    rootHash: str
    accessMode: str
    enabled: bool
    availability: str


@dataclass(frozen=True, slots=True)
class PreparedRun:
    run_id: str
    system_prompt: str
    model_limits: ModelLimits
    selection: ExecutionPluginSelection
    reasoning_resolution: ReasoningResolution
    provider_endpoint: ProviderEndpointSnapshot | None = None
    workspace_availability: WorkspaceAvailability = WorkspaceAvailability.NOT_APPLICABLE
    workspace_mounts: tuple[StartedMount, ...] = ()
    request_observer: ModelRequestObserver | None = field(default=None, repr=False)


class RunPreparation(Protocol):
    async def prepare(self, run: RunSnapshot) -> PreparedRun: ...
