"""Static checks for the authoritative AI settings HTTP contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "ai-settings.openapi.json"
)


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_is_openapi_31_json() -> None:
    contract = load_contract()

    assert contract["openapi"] == "3.1.0"
    assert contract["info"]["version"] == "0.5.0-draft"
    assert contract["security"] == []


def test_contract_has_only_the_approved_ai_settings_operations() -> None:
    contract = load_contract()
    operations = {
        (path, method)
        for path, path_item in contract["paths"].items()
        for method in path_item
        if method in {"get", "put", "post", "delete", "patch"}
    }

    assert operations == {
        ("/api/settings/ai", "get"),
        ("/api/settings/ai", "put"),
    }


def test_ai_settings_schema_persists_model_response_and_continuation() -> None:
    schemas = load_contract()["components"]["schemas"]
    selection = schemas["ModelSelection"]

    assert selection["additionalProperties"] is False
    assert selection["required"] == [
        "providerId",
        "modelId",
        "contextBudget",
        "outputBudget",
    ]
    assert set(selection["properties"]) == {
        "providerId",
        "modelId",
        "contextBudget",
        "outputBudget",
    }
    assert selection["properties"]["contextBudget"]["enum"] == [
        "auto",
        "32k",
        "64k",
        "128k",
        "256k",
        "max",
    ]
    assert selection["properties"]["outputBudget"]["enum"] == [
        "auto",
        "8k",
        "16k",
        "32k",
        "64k",
        "max",
    ]
    assert selection["properties"]["modelId"]["minLength"] == 1
    assert selection["properties"]["modelId"]["maxLength"] == 256
    settings = schemas["AiSettings"]
    assert settings["additionalProperties"] is False
    assert settings["required"] == ["model", "responseMode", "autoContinueOutput"]
    assert set(settings["properties"]) == {"model", "responseMode", "autoContinueOutput"}
    assert settings["properties"]["autoContinueOutput"]["type"] == "boolean"
    assert schemas["ResponseMode"]["enum"] == ["default", "fast", "balanced", "deep"]
    assert schemas["ErrorCode"]["enum"] == [
        "invalid_request",
        "not_connected",
        "credential_store_unavailable",
        "settings_store_unavailable",
        "internal_error",
    ]


def test_put_error_mapping_is_explicit() -> None:
    responses = load_contract()["paths"]["/api/settings/ai"]["put"][
        "responses"
    ]

    assert responses["400"]["$ref"].endswith("/InvalidRequest")
    assert responses["409"]["$ref"].endswith("/NotConnected")
    assert responses["503"]["$ref"].endswith(
        "/SettingsOrCredentialStoreUnavailable"
    )
    assert responses["500"]["$ref"].endswith("/InternalError")
