"""Static checks for the authoritative schedule contract."""

import json
from pathlib import Path

from opensprite_backend.app import create_app


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "schedules.openapi.json"


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_contains_only_approved_schedule_operations() -> None:
    contract = load_contract()
    assert contract["openapi"] == "3.1.0"
    paths = contract["paths"]
    assert set(paths) == {
        "/api/schedules",
        "/api/schedules/runtime-status",
        "/api/schedules/{schedule_id}",
        "/api/schedules/{schedule_id}/pause",
        "/api/schedules/{schedule_id}/resume",
        "/api/schedules/{schedule_id}/run-now",
        "/api/schedules/{schedule_id}/occurrences",
    }
    schemas = contract["components"]["schemas"]
    assert schemas["RuntimeStatus"]["properties"]["continuity"]["enum"] == [
        "linger_enabled",
        "login_only",
        "unknown",
    ]


def test_generated_operation_ids_match_schedule_contract() -> None:
    contract = load_contract()
    generated = create_app().openapi()
    for path, methods in contract["paths"].items():
        for method, operation in methods.items():
            assert generated["paths"][path][method]["operationId"] == operation[
                "operationId"
            ]
    generated_schemas = generated["components"]["schemas"]
    assert generated_schemas["CreateScheduleRequest"]["additionalProperties"] is False
    assert generated_schemas["UpdateScheduleRequest"]["additionalProperties"] is False
    assert generated_schemas["RevisionRequest"]["additionalProperties"] is False
