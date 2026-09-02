"""Contract checks for the local path picker."""

import json
from pathlib import Path

from opensprite_backend.app import create_app


CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "local-paths.openapi.json"


def test_local_path_contract_is_strict_and_matches_operation() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    operation = contract["paths"]["/api/local-paths/pick"]["post"]
    assert operation["operationId"] == "pickLocalPath"
    request = contract["components"]["schemas"]["LocalPathPickRequest"]
    assert request["additionalProperties"] is False
    assert request["properties"]["kind"]["enum"] == ["executable", "directory"]
    assert "initialPath" not in json.dumps(contract)


def test_generated_openapi_contains_local_path_picker_operation() -> None:
    generated = create_app().openapi()
    assert generated["paths"]["/api/local-paths/pick"]["post"]["operationId"] == "pickLocalPath"
