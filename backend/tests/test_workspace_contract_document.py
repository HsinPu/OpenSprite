"""Static checks for the authoritative Workspace HTTP contract."""

import json
from pathlib import Path

from opensprite_backend.app import create_app


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "contracts" / "workspaces.openapi.json"
)


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_workspace_contract_operations_and_strict_shapes() -> None:
    contract = load_contract()
    assert contract["openapi"] == "3.1.0"
    paths = contract["paths"]  # type: ignore[index]
    assert set(paths) == {
        "/api/workspaces",
        "/api/workspaces/import-candidates",
        "/api/workspaces/import",
        "/api/workspaces/active",
        "/api/workspaces/{workspace_id}",
        "/api/workspaces/{workspace_id}/mounts",
        "/api/workspaces/{workspace_id}/mounts/{mount_id}",
    }
    assert paths["/api/workspaces"]["get"]["operationId"] == "listWorkspaces"  # type: ignore[index]
    assert paths["/api/workspaces"]["post"]["operationId"] == "createWorkspace"  # type: ignore[index]
    assert paths["/api/workspaces/active"]["put"]["operationId"] == "setActiveWorkspace"  # type: ignore[index]
    schemas = contract["components"]["schemas"]  # type: ignore[index]
    for name in (
        "CreateWorkspaceRequest",
        "ImportWorkspaceRequest",
        "UpdateWorkspaceRequest",
        "MountWorkspaceRequest",
        "SetActiveWorkspaceRequest",
        "WorkspaceUsage",
        "Workspace",
        "WorkspaceCatalog",
        "WorkspaceError",
    ):
        assert schemas[name]["additionalProperties"] is False
    assert schemas["Workspace"]["properties"]["kind"]["enum"] == ["default", "managed"]  # type: ignore[index]
    assert schemas["WorkspaceMount"]["properties"]["accessMode"]["enum"] == ["read_only", "read_write"]  # type: ignore[index]


def test_workspace_contract_has_explicit_conflict_and_store_failures() -> None:
    contract = load_contract()
    errors = contract["components"]["schemas"]["WorkspaceErrorCode"]["enum"]  # type: ignore[index]
    assert errors == [
        "invalid_request",
        "invalid_directory_name",
        "unsafe_root",
        "duplicate_name",
        "duplicate_root",
        "managed_root_exists",
        "mount_limit_reached",
        "duplicate_mount_alias",
        "overlapping_root",
        "revision_conflict",
        "not_found",
        "mount_not_found",
        "workspace_busy",
        "workspace_not_empty",
        "workspace_store_unavailable",
        "internal_error",
    ]
    create_responses = contract["paths"]["/api/workspaces"]["post"]["responses"]  # type: ignore[index]
    assert set(create_responses) == {"201", "400", "409", "503"}


def test_live_openapi_keeps_the_workspace_delete_revision_parameter() -> None:
    operation = create_app().openapi()["paths"]["/api/workspaces/{workspace_id}"]["delete"]
    parameters = {
        (item["name"], item["in"], item["required"])
        for item in operation["parameters"]
    }

    assert ("workspace_id", "path", True) in parameters
    assert ("expectedRevision", "query", True) in parameters
