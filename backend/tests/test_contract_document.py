"""Static checks for the authoritative provider-connections contract."""

import json
from pathlib import Path
from typing import Any

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "provider-connections.openapi.json"
)


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_is_openapi_31_json() -> None:
    contract = load_contract()

    assert contract["openapi"] == "3.1.0"
    assert contract["info"]["version"] == "0.1.0-draft"
    assert contract["security"] == []


def test_contract_has_only_the_approved_operations() -> None:
    contract = load_contract()
    operations = {
        (path, method)
        for path, path_item in contract["paths"].items()
        for method in path_item
        if method in {"get", "put", "post", "delete", "patch"}
    }

    assert operations == {
        ("/healthz", "get"),
        ("/api/providers", "get"),
        ("/api/providers/{provider_id}/connection", "put"),
        ("/api/providers/{provider_id}/connection", "delete"),
        ("/api/providers/{provider_id}/connection/test", "post"),
    }


def test_public_summary_and_error_fields_are_fixed() -> None:
    schemas = load_contract()["components"]["schemas"]

    assert schemas["ProviderSummary"]["required"] == [
        "id",
        "name",
        "connected",
        "status",
        "credentialPreview",
        "lastCheckedAt",
    ]
    assert schemas["ProviderSummary"]["additionalProperties"] is False
    assert schemas["PutProviderConnectionRequest"]["properties"]["apiKey"][
        "writeOnly"
    ] is True
    assert schemas["ErrorDetail"]["required"] == [
        "code",
        "message",
        "retryable",
    ]


def test_provider_catalog_schema_fixes_identity_name_and_order() -> None:
    providers = load_contract()["components"]["schemas"][
        "ProviderListResponse"
    ]["properties"]["providers"]

    assert providers["minItems"] == 2
    assert providers["maxItems"] == 2
    assert providers["items"] is False
    assert [
        (
            item["allOf"][1]["properties"]["id"]["const"],
            item["allOf"][1]["properties"]["name"]["const"],
        )
        for item in providers["prefixItems"]
    ] == [("openai", "OpenAI"), ("anthropic", "Anthropic")]


def test_error_status_mapping_is_explicit() -> None:
    paths = load_contract()["paths"]
    put_responses = paths["/api/providers/{provider_id}/connection"]["put"][
        "responses"
    ]
    test_responses = paths[
        "/api/providers/{provider_id}/connection/test"
    ]["post"]["responses"]

    assert put_responses["400"]["$ref"].endswith("/InvalidRequest")
    assert put_responses["404"]["$ref"].endswith("/UnsupportedProvider")
    assert put_responses["422"]["$ref"].endswith("/InvalidCredentials")
    assert put_responses["502"]["$ref"].endswith("/ProviderUnreachable")
    assert put_responses["503"]["$ref"].endswith(
        "/CredentialStoreUnavailable"
    )
    assert put_responses["504"]["$ref"].endswith("/ProviderTimeout")
    assert put_responses["500"]["$ref"].endswith("/InternalError")
    assert test_responses["409"]["$ref"].endswith("/NotConnected")
