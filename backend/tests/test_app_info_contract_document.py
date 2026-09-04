from __future__ import annotations

import json
from pathlib import Path

from opensprite_backend.app import create_app

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "app-info.openapi.json"


def test_app_info_contract_matches_generated_route_and_schema() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    generated = create_app().openapi()

    assert contract["openapi"] == "3.1.0"
    assert contract["paths"]["/api/app-info"]["get"]["operationId"] == "getAppInfo"
    expected = contract["components"]["schemas"]["AppInfo"]
    actual = generated["components"]["schemas"]["AppInfo"]
    assert actual["additionalProperties"] is False
    assert actual["required"] == expected["required"]
    assert set(actual["properties"]) == set(expected["properties"])


def test_product_version_has_one_authoritative_value() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.11.0"' in pyproject
    assert create_app().version == "0.11.0"
