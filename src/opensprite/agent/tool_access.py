"""Single entry point for resolving effective tool access policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..tools import BatchTool, ToolRegistry
from ..tools.permissions import CompositeToolPermissionPolicy, ToolPermissionPolicy
from .harness_policy import HarnessPolicy, HarnessPolicyService


@dataclass(frozen=True)
class ToolAccessResolution:
    """Resolved tool registry and metadata for one agent turn."""

    registry: ToolRegistry
    effective_policy: ToolPermissionPolicy
    metadata: dict[str, Any]


class ToolAccessResolver:
    """Resolve global, profile, and harness permissions into executable tool access."""

    def __init__(self, *, harness_policies: HarnessPolicyService | None = None):
        self._harness_policies = harness_policies or HarnessPolicyService()

    def resolve(
        self,
        base_registry: ToolRegistry,
        harness_policy: HarnessPolicy,
        profile_permission_policy: ToolPermissionPolicy | None = None,
    ) -> ToolAccessResolution:
        """Return a registry constrained by the selected effective tool policy."""
        policies = [base_registry.permission_policy]
        if profile_permission_policy is not None:
            policies.append(profile_permission_policy)
        policies.append(harness_policy.to_permission_policy())
        effective_policy = CompositeToolPermissionPolicy(*policies)
        registry = base_registry.filtered(permission_policy=effective_policy)
        metadata = self._harness_policies.policy_resolution_metadata(
            base_registry.permission_policy,
            profile_permission_policy,
            harness_policy,
            effective_policy,
        )
        registry.permission_resolution_metadata = metadata
        if "batch" in registry.tool_names:
            registry.register(BatchTool(registry_resolver=lambda: registry))
        return ToolAccessResolution(
            registry=registry,
            effective_policy=effective_policy,
            metadata=metadata,
        )
