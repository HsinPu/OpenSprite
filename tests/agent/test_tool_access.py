from opensprite.tools.access import ToolAccessResolver
from opensprite.tools.base import Tool
from opensprite.tools.permissions import ToolPermissionPolicy
from opensprite.tools.registry import ToolRegistry


class DummyTool(Tool):
    def __init__(self, name: str, *, risk_levels: frozenset[str] | None = None):
        self._name = name
        self._risk_levels = risk_levels

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Dummy {self._name} tool"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    @property
    def risk_levels(self) -> frozenset[str] | None:
        return self._risk_levels

    async def _execute(self, **kwargs) -> str:
        return "ok"


def _registry(permission_policy: ToolPermissionPolicy | None = None) -> ToolRegistry:
    registry = ToolRegistry(permission_policy=permission_policy)
    for name in ("read_file", "web_search", "apply_patch", "task_update", "batch"):
        registry.register(DummyTool(name))
    return registry


def test_tool_access_resolver_resolves_overlay_policy_and_metadata():
    registry = _registry()
    overlay = ToolPermissionPolicy(
        allowed_tools=["read_file", "batch"],
        allowed_risk_levels=["read"],
        denied_risk_levels=["write", "network"],
    )

    resolution = ToolAccessResolver().resolve_overlay(
        registry,
        overlay_policy=overlay,
        include_names={"read_file", "web_search", "apply_patch", "batch"},
        metadata_kind="planning",
    )

    assert resolution.registry.tool_names == ["read_file", "batch"]
    assert resolution.registry.permission_policy is resolution.effective_policy
    assert resolution.registry.permission_resolution_metadata == resolution.metadata
    assert resolution.metadata["kind"] == "planning"
    assert resolution.metadata["overlay_permission_policy"]["allowed_tools"] == ["read_file", "batch"]
    assert resolution.metadata["effective_risks"]["allowed_risk_levels"] == ["read"]
    blocked = {item["name"]: item for item in resolution.metadata["tool_access"]["blocked_tools"]}
    assert blocked["web_search"]["reason"] == "tool 'web_search' is not in allowed_tools"
    assert blocked["apply_patch"]["reason"] == "tool 'apply_patch' is not in allowed_tools"


def test_tool_access_resolver_resolves_overlay_policy_without_registry():
    base = ToolPermissionPolicy(allowed_risk_levels=["read", "network"])
    overlay = ToolPermissionPolicy(allowed_risk_levels=["read"])

    resolution = ToolAccessResolver().resolve_overlay_policy(
        base,
        overlay_policy=overlay,
        metadata_kind="profile_override:chat",
    )

    assert resolution.metadata["kind"] == "profile_override:chat"
    assert resolution.metadata["base_permission_policy"]["allowed_risk_levels"] == ["network", "read"]
    assert resolution.metadata["overlay_permission_policy"]["allowed_risk_levels"] == ["read"]
    assert resolution.metadata["effective_risks"]["allowed_risk_levels"] == ["read"]
    assert "network" in resolution.metadata["effective_risks"]["denied_risk_levels"]


def test_tool_access_resolver_exposes_only_required_tools_with_user_permissions():
    resolution = ToolAccessResolver().resolve_required_tools(
        _registry(),
        ("read_file", "apply_patch", "read_file"),
    )

    assert resolution.registry.tool_names == ["read_file", "apply_patch"]
    assert resolution.registry.permission_policy is resolution.effective_policy
    assert resolution.registry.permission_resolution_metadata == resolution.metadata
    assert resolution.metadata["kind"] == "task_contract_required_tools"
    assert resolution.metadata["required_tools"] == ["read_file", "apply_patch"]
    assert resolution.metadata["tool_access"]["exposed_tools"] == ["read_file", "apply_patch"]
    assert resolution.metadata["blocked_required_tools"] == []


def test_tool_access_resolver_user_permission_blocks_required_tools():
    policy = ToolPermissionPolicy(allowed_tools=["read_file"])
    resolution = ToolAccessResolver().resolve_required_tools(
        _registry(policy),
        ("read_file", "apply_patch"),
    )

    assert resolution.registry.tool_names == ["read_file"]
    blocked = {item["name"]: item for item in resolution.metadata["blocked_required_tools"]}
    assert blocked["apply_patch"]["registered"] is True
    assert blocked["apply_patch"]["reason"] == "tool 'apply_patch' is not in allowed_tools"


def test_tool_access_resolver_reports_missing_required_tools():
    resolution = ToolAccessResolver().resolve_required_tools(
        _registry(),
        ("read_file", "missing_tool"),
    )

    assert resolution.registry.tool_names == ["read_file"]
    blocked = {item["name"]: item for item in resolution.metadata["blocked_required_tools"]}
    assert blocked["missing_tool"] == {
        "name": "missing_tool",
        "registered": False,
        "exposed": False,
        "reason": "tool is not registered",
        "risk_levels": [],
        "requires_approval": False,
    }
