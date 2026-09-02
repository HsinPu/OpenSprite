"""Static checks for the authoritative tool settings contract."""

import json
from pathlib import Path

from opensprite_backend.app import create_app


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "tool-settings.openapi.json"
)


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_has_only_approved_operations_and_values() -> None:
    contract = load_contract()
    assert contract["openapi"] == "3.1.0"
    paths = contract["paths"]  # type: ignore[index]
    assert set(paths) == {"/api/tools", "/api/settings/tools"}  # type: ignore[arg-type]
    assert set(paths["/api/tools"]) == {"get"}  # type: ignore[index]
    assert set(paths["/api/settings/tools"]) == {"get", "put"}  # type: ignore[index]
    schemas = contract["components"]["schemas"]  # type: ignore[index]
    settings = schemas["ToolSettings"]
    assert settings["additionalProperties"] is False
    assert settings["required"] == ["enabled", "enabledTools"]
    assert schemas["ToolSource"]["enum"] == ["builtin", "mcp", "external"]
    assert schemas["ErrorCode"]["enum"] == [
        "invalid_request",
        "tool_not_found",
        "settings_store_unavailable",
        "internal_error",
    ]


def test_put_error_mapping_is_explicit() -> None:
    contract = load_contract()
    responses = contract["paths"]["/api/settings/tools"]["put"]["responses"]  # type: ignore[index]
    assert responses["400"]["$ref"].endswith("/InvalidRequest")
    assert responses["503"]["$ref"].endswith("/SettingsStoreUnavailable")
    assert responses["500"]["$ref"].endswith("/InternalError")


def test_generated_routes_and_public_models_match_contract() -> None:
    contract = load_contract()
    generated = create_app().openapi()

    assert generated["paths"]["/api/tools"]["get"]["operationId"] == "listTools"
    assert generated["paths"]["/api/settings/tools"]["get"]["operationId"] == "getToolSettings"
    assert generated["paths"]["/api/settings/tools"]["put"]["operationId"] == "putToolSettings"
    generated_schemas = generated["components"]["schemas"]
    contract_schemas = contract["components"]["schemas"]  # type: ignore[index]
    for generated_name, contract_name in (
        ("ToolSummary", "ToolSummary"),
        ("ToolListResponse", "ToolListResponse"),
        ("ToolSettings", "ToolSettings"),
        ("ToolSettingsErrorDetail", "ErrorDetail"),
        ("ToolSettingsErrorEnvelope", "ErrorEnvelope"),
    ):
        assert generated_schemas[generated_name]["required"] == contract_schemas[contract_name]["required"]
