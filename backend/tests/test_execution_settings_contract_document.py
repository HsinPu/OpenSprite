"""Scope and shape checks for the execution settings contract."""

import json
from pathlib import Path


def test_execution_contract_has_only_selection_and_metadata_operations() -> None:
    document = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "execution-settings.openapi.json").read_text(encoding="utf-8"))
    assert document["openapi"] == "3.1.0"
    assert set(document["paths"]) == {"/api/settings/execution"}
    assert set(document["paths"]["/api/settings/execution"]) == {"get", "put"}
    schemas = document["components"]["schemas"]
    assert schemas["ExecutionSelection"]["required"] == ["loopId", "policyId"]
    assert schemas["ExecutionSelection"]["additionalProperties"] is False
    assert set(schemas["ExecutionSelection"]["properties"]) == {"loopId", "policyId"}
    assert schemas["ExecutionPlugin"]["properties"]["kind"]["enum"] == ["loop", "policy"]
    assert schemas["ExecutionPlugin"]["properties"]["status"]["enum"] == ["available", "incompatible", "unavailable"]
    assert schemas["ExecutionPlugin"]["properties"]["apiVersion"] == {"type": "integer", "minimum": 1}
    assert document["x-persistence"]["default"] == {"loopId": "standard", "policyId": "standard"}
    responses = document["paths"]["/api/settings/execution"]["put"]["responses"]
    assert responses["400"]["$ref"].endswith("/InvalidRequest")
    assert responses["503"]["$ref"].endswith("/Unavailable")
