"""Tool selection resolution for task-required tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..tool_names import BATCH_TOOL_NAME
from .batch import BatchTool
from .registry import ToolRegistry


@dataclass(frozen=True)
class ToolSelectionResolution:
    """Resolved tool registry and metadata for one agent turn."""

    registry: ToolRegistry
    metadata: dict[str, Any]


class ToolSelectionResolver:
    """Resolve task-required tools and explicit tool subsets into executable registries."""

    def resolve_required_tools(
        self,
        base_registry: ToolRegistry,
        required_tools: Any,
        *,
        metadata_kind: str = "task_contract_required_tools",
    ) -> ToolSelectionResolution:
        """Return a registry containing only task-required tools that are registered."""
        required_tool_names = _normalize_required_tool_names(required_tools)
        registry = base_registry.filtered(include_names=set(required_tool_names), exposed_only=True)
        _ensure_batch_tool(registry)
        metadata = _selection_metadata(
            base_registry,
            registry,
            required_tool_names,
            metadata_kind=metadata_kind,
        )
        registry.tool_selection_metadata = metadata
        return ToolSelectionResolution(registry=registry, metadata=metadata)

    def resolve_overlay(
        self,
        base_registry: ToolRegistry,
        *,
        include_names: set[str] | frozenset[str] | None = None,
        metadata_kind: str,
        **_: Any,
    ) -> ToolSelectionResolution:
        """Return a registry constrained to an explicit tool subset."""
        requested_tool_names = tuple(sorted(str(name) for name in include_names)) if include_names is not None else tuple(base_registry.tool_names)
        registry = base_registry.filtered(include_names=set(requested_tool_names) if include_names is not None else None, exposed_only=True)
        _ensure_batch_tool(registry)
        metadata = _selection_metadata(
            base_registry,
            registry,
            requested_tool_names,
            metadata_kind=metadata_kind,
        )
        registry.tool_selection_metadata = metadata
        return ToolSelectionResolution(registry=registry, metadata=metadata)


def _ensure_batch_tool(registry: ToolRegistry) -> None:
    if BATCH_TOOL_NAME in registry.tool_names:
        registry.register(BatchTool(registry_resolver=lambda: registry))


def _selection_metadata(
    base_registry: ToolRegistry,
    resolved_registry: ToolRegistry,
    requested_tool_names: tuple[str, ...],
    *,
    metadata_kind: str,
) -> dict[str, Any]:
    selected_tools = list(resolved_registry.tool_names)
    missing_required_tools = _missing_required_tool_metadata(base_registry, requested_tool_names)
    tool_selection = {
        "registered_tool_count": len(base_registry.registered_tools()),
        "selected_tool_count": len(selected_tools),
        "missing_required_tool_count": len(missing_required_tools),
        "selected_tools": selected_tools,
        "missing_required_tools": missing_required_tools,
    }
    return {
        "schema_version": 2,
        "kind": metadata_kind,
        "required_tools": list(requested_tool_names),
        "tool_selection": tool_selection,
        "blocked_required_tools": missing_required_tools,
    }


def _normalize_required_tool_names(required_tools: Any) -> tuple[str, ...]:
    if required_tools is None:
        return ()
    if isinstance(required_tools, str):
        values = [required_tools]
    else:
        try:
            values = list(required_tools)
        except TypeError:
            return ()
    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = str(value or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return tuple(names)


def _missing_required_tool_metadata(
    base_registry: ToolRegistry,
    required_tool_names: tuple[str, ...],
) -> list[dict[str, Any]]:
    missing_tools: list[dict[str, Any]] = []
    for tool_name in required_tool_names:
        if base_registry.get(tool_name) is not None:
            continue
        missing_tools.append(
            {
                "name": tool_name,
                "registered": False,
                "selected": False,
                "reason": "tool is not registered",
            }
        )
    return missing_tools
