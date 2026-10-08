"""Metadata-only discovery; load one trusted Loop factory at Run admission."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from importlib.metadata import EntryPoint, entry_points
import inspect
import re
from threading import RLock
from typing import Literal

from .builtin_plugins import BuiltinLoopFactory
from .plugin import AgentLoopPlugin, AgentLoopPluginFactory

PluginStatus = Literal["available", "incompatible", "unavailable"]
API_VERSION = 3
_GROUP = re.compile(r"^opensprite_backend\.agent_loops\.v([1-9][0-9]*)$")
_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class ExecutionPluginError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    id: str
    name: str
    description: str
    version: str
    api_version: int
    status: PluginStatus = "available"


@dataclass(frozen=True, slots=True)
class _EntryPointSource:
    point: EntryPoint


@dataclass(frozen=True, slots=True)
class ExecutionPluginSelection:
    plugin_id: str
    plugin_version: str
    factory: AgentLoopPluginFactory = field(repr=False)

    def create(self) -> AgentLoopPlugin:
        try:
            plugin = self.factory.create()
            if inspect.iscoroutine(plugin):
                plugin.close()
                raise ValueError("create must return a plugin synchronously")
            if not inspect.iscoroutinefunction(getattr(plugin, "execute", None)):
                raise ValueError("execute must be async")
            for method in ("allow_context_retry", "allow_output_continuation"):
                callback = getattr(plugin, method, None)
                if not callable(callback) or inspect.iscoroutinefunction(callback):
                    raise ValueError("decisions must be synchronous")
            return plugin
        except (Exception, asyncio.CancelledError):
            raise ExecutionPluginError("plugin_unavailable") from None

    def profile(self) -> dict[str, object]:
        return {"pluginId": self.plugin_id, "pluginVersion": self.plugin_version,
                "apiVersion": API_VERSION}


class ExecutionPluginCatalog:
    def __init__(self, discovered: tuple[EntryPoint, ...] | None = None) -> None:
        self._load_lock = RLock()
        self._descriptors: dict[str, PluginDescriptor] = {}
        self._sources: dict[str, object] = {}
        for descriptor, factory in (
            (PluginDescriptor("standard", "Standard Loop", "Text execution with bounded recovery and configured continuation.", "3.0.0", API_VERSION), BuiltinLoopFactory()),
            (PluginDescriptor("no_recovery", "No automatic recovery", "Text execution without context retry or output continuation.", "3.0.0", API_VERSION), BuiltinLoopFactory(True)),
        ):
            self._descriptors[descriptor.id] = descriptor
            self._sources[descriptor.id] = factory
        if discovered is None:
            all_points = entry_points()
            discovered = tuple(point for group in all_points.groups
                               if _GROUP.fullmatch(group) for point in all_points.select(group=group))
        # Retired policy entry points are not an executable plugin category.
        for point in discovered:
            match = _GROUP.fullmatch(point.group)
            if match is None or _ID.fullmatch(point.name) is None:
                continue
            identifier = point.name
            if identifier in self._descriptors:
                self._descriptors[identifier] = replace(self._descriptors[identifier], status="unavailable")
                self._sources.pop(identifier, None)
                continue
            api_version = int(match[1])
            version, description = "unknown", ""
            metadata_available = True
            try:
                distribution = point.dist
                if distribution is not None:
                    metadata = distribution.metadata
                    raw_version = metadata.get("Version")
                    if not isinstance(raw_version, str) or not raw_version.strip() or len(raw_version) > 64:
                        raise ValueError("invalid plugin version metadata")
                    version = raw_version
                    raw_description = metadata.get("Summary", "")
                    if not isinstance(raw_description, str):
                        raise ValueError("invalid plugin summary metadata")
                    description = raw_description[:256]
            except Exception:
                metadata_available = False
            status: PluginStatus = ("unavailable" if not metadata_available else
                                    "available" if api_version == API_VERSION else "incompatible")
            self._descriptors[identifier] = PluginDescriptor(identifier, identifier, description,
                                                           version, api_version, status)
            self._sources[identifier] = _EntryPointSource(point)

    def descriptors(self) -> tuple[PluginDescriptor, ...]:
        with self._load_lock:
            return tuple(self._descriptors.values())

    def _descriptor(self, identifier: str) -> PluginDescriptor:
        if not isinstance(identifier, str) or _ID.fullmatch(identifier) is None:
            raise ExecutionPluginError("invalid_request")
        descriptor = self._descriptors.get(identifier)
        if descriptor is None:
            raise ExecutionPluginError("invalid_request")
        if descriptor.status != "available":
            raise ExecutionPluginError("plugin_unavailable")
        return descriptor

    def validate_selection(self, plugin_id: str) -> None:
        with self._load_lock:
            self._descriptor(plugin_id)

    def resolve(self, plugin_id: str) -> ExecutionPluginSelection:
        with self._load_lock:
            descriptor = self._descriptor(plugin_id)
            try:
                source = self._sources[plugin_id]
                if isinstance(source, _EntryPointSource):
                    provider = source.point.load()
                    if not callable(provider) or inspect.iscoroutinefunction(provider):
                        raise ValueError("factory provider must be synchronous")
                    factory = provider()
                    if inspect.iscoroutine(factory):
                        factory.close()
                        raise ValueError("factory provider returned a coroutine")
                else:
                    factory = source
                if (type(getattr(factory, "api_version", None)) is not int
                    or factory.api_version != API_VERSION or not callable(getattr(factory, "create", None))
                    or inspect.iscoroutinefunction(factory.create)):
                    raise ValueError("invalid factory")
                self._sources[plugin_id] = factory
                return ExecutionPluginSelection(descriptor.id, descriptor.version, factory)
            except (Exception, asyncio.CancelledError):
                self._descriptors[plugin_id] = replace(descriptor, status="unavailable")
                raise ExecutionPluginError("plugin_unavailable") from None
