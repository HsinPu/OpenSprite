"""Versioned discovery of trusted, installed Agent execution plugins.

Discovery reads package metadata only. Selected entry points are loaded at the
acceptance boundary; Python plugins run with the backend's process privileges.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from importlib.metadata import EntryPoint, entry_points
import re
from threading import RLock
from typing import Literal, Protocol

from .driver import AgentDriverFactory
from .standard_driver import StandardDriverFactory
from .strategies import ExecutionStrategy, NoRecoveryExecutionStrategy, StandardExecutionStrategy

PluginKind = Literal["loop", "policy"]
PluginStatus = Literal["available", "incompatible", "unavailable"]
API_VERSION = 2
_GROUP = re.compile(r"^opensprite_backend\.(agent_loops|execution_policies)\.v([1-9][0-9]*)$")
_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class ExecutionPluginError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    id: str
    kind: PluginKind
    name: str
    description: str
    version: str
    api_version: int
    status: PluginStatus = "available"


class ExecutionStrategyFactory(Protocol):
    api_version: int

    def create(self) -> ExecutionStrategy: ...


@dataclass(frozen=True, slots=True)
class _EntryPointSource:
    point: EntryPoint


@dataclass(frozen=True, slots=True)
class _StrategyFactory:
    no_recovery: bool = False
    api_version: int = API_VERSION

    def create(self) -> ExecutionStrategy:
        return NoRecoveryExecutionStrategy() if self.no_recovery else StandardExecutionStrategy()


@dataclass(frozen=True, slots=True)
class ExecutionPluginSelection:
    loop_id: str
    loop_version: str
    policy_id: str
    policy_version: str
    driver_factory: AgentDriverFactory = field(repr=False)
    strategy_factory: ExecutionStrategyFactory = field(repr=False)

    def make_strategy(self) -> ExecutionStrategy:
        try:
            strategy = self.strategy_factory.create()
            if not all(callable(getattr(strategy, method, None)) for method in
                       ("allow_context_retry", "allow_output_continuation")):
                raise ExecutionPluginError("plugin_unavailable")
            return strategy
        except Exception:
            raise ExecutionPluginError("plugin_unavailable") from None

    def profile(self) -> dict[str, object]:
        return {
            "loopId": self.loop_id, "loopVersion": self.loop_version,
            "policyId": self.policy_id, "policyVersion": self.policy_version,
            "apiVersion": API_VERSION,
        }


class ExecutionPluginCatalog:
    def __init__(self, discovered: tuple[EntryPoint, ...] | None = None) -> None:
        self._load_lock = RLock()
        self._descriptors: dict[tuple[PluginKind, str], PluginDescriptor] = {}
        self._sources: dict[tuple[PluginKind, str], object] = {}
        for descriptor, factory in (
            (PluginDescriptor("standard", "loop", "Standard Loop", "Model turns through the core host.", "2.0.0", API_VERSION), StandardDriverFactory()),
            (PluginDescriptor("standard", "policy", "Standard", "Bounded context retry and configured output continuation.", "2.0.0", API_VERSION), _StrategyFactory()),
            (PluginDescriptor("no_recovery", "policy", "No automatic recovery", "Disable context retry and output continuation.", "2.0.0", API_VERSION), _StrategyFactory(True)),
        ):
            key = (descriptor.kind, descriptor.id)
            self._descriptors[key] = descriptor
            self._sources[key] = factory
        if discovered is None:
            # Iterating groups supports reporting unsupported API versions too.
            all_points = entry_points()
            discovered = tuple(point for group in all_points.groups
                               if _GROUP.fullmatch(group) for point in all_points.select(group=group))
        for point in discovered:
            match = _GROUP.fullmatch(point.group)
            if match is None or _ID.fullmatch(point.name) is None:
                continue
            kind: PluginKind = "loop" if match[1] == "agent_loops" else "policy"
            key = (kind, point.name)
            if key in self._descriptors:
                self._descriptors[key] = replace(self._descriptors[key], status="unavailable")
                self._sources.pop(key, None)
                continue
            api_version = int(match[2])
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
            status: PluginStatus = (
                "unavailable" if not metadata_available else
                "available" if api_version == API_VERSION else "incompatible"
            )
            descriptor = PluginDescriptor(point.name, kind, point.name, description,
                                          version, api_version, status)
            self._descriptors[key] = descriptor
            self._sources[key] = _EntryPointSource(point)

    def descriptors(self) -> tuple[PluginDescriptor, ...]:
        return tuple(self._descriptors.values())

    def _factory(self, kind: PluginKind, identifier: str):
        with self._load_lock:
            return self._load_factory(kind, identifier)

    def _load_factory(self, kind: PluginKind, identifier: str):
        if not isinstance(identifier, str) or _ID.fullmatch(identifier) is None:
            raise ExecutionPluginError("invalid_request")
        key = (kind, identifier)
        descriptor = self._descriptors.get(key)
        if descriptor is None:
            raise ExecutionPluginError("invalid_request")
        if descriptor.status != "available":
            raise ExecutionPluginError("plugin_unavailable")
        try:
            source = self._sources[key]
            # External entry points export a no-argument factory provider.
            factory = source.point.load()() if isinstance(source, _EntryPointSource) else source
            if type(getattr(factory, "api_version", None)) is not int or factory.api_version != API_VERSION or not callable(getattr(factory, "create", None)):
                raise ExecutionPluginError("plugin_unavailable")
            self._sources[key] = factory
            return descriptor, factory
        except (Exception, asyncio.CancelledError):
            self._descriptors[key] = replace(descriptor, status="unavailable")
            raise ExecutionPluginError("plugin_unavailable") from None

    def resolve(self, loop_id: str, policy_id: str) -> ExecutionPluginSelection:
        loop, driver = self._factory("loop", loop_id)
        policy, strategy = self._factory("policy", policy_id)
        return ExecutionPluginSelection(loop.id, loop.version, policy.id, policy.version, driver, strategy)

    def validate_selection(self, loop_id: str, policy_id: str) -> None:
        self.resolve(loop_id, policy_id)
