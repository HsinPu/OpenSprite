import json
import re
from pathlib import Path

from opensprite_backend.app import create_app
from opensprite_backend.authentication.middleware import SESSION_COOKIE


def test_custom_provider_contract_matches_routes_and_secret_boundary():
    document = json.loads((Path(__file__).parents[2] / "contracts/custom-providers.openapi.json").read_text(encoding="utf-8"))
    runtime = create_app().openapi()
    assert document["info"]["version"] == "0.21.0"
    assert document["components"]["securitySchemes"]["localSession"]["name"] == SESSION_COOKIE
    for path, operations in document["paths"].items():
        for method, operation in operations.items():
            if method == "parameters":
                continue
            assert runtime["paths"][path][method]["operationId"] == operation["operationId"]
            assert operation["security"] == [{"localSession": []}]
    schemas = document["components"]["schemas"]
    assert schemas["ProviderCreate"]["properties"]["apiKey"]["writeOnly"] is True
    assert "apiKey" not in schemas["Provider"]["properties"]
    for schema in schemas.values():
        assert schema["additionalProperties"] is False


def test_consumer_contracts_accept_custom_provider_identity():
    contracts = Path(__file__).parents[2] / "contracts"
    custom_id = "12345678-1234-4234-8234-123456789abc"
    for filename in ("agent-chat", "ai-settings", "provider-connections", "schedules"):
        document = json.loads((contracts / f"{filename}.openapi.json").read_text(encoding="utf-8"))
        schemas = document["components"]["schemas"]
        identity = (schemas["ExecutionProfile"]["properties"]["providerId"]
                    if filename == "schedules" else schemas["ProviderId"])
        for accepted in ("openai", "anthropic", "openrouter", custom_id):
            assert re.fullmatch(identity["pattern"], accepted)
        for rejected in ("custom", "", custom_id.upper(), "12345678-1234-1234-8234-123456789abc"):
            assert not re.fullmatch(identity["pattern"], rejected)
        if filename == "provider-connections":
            listing = schemas["ProviderListResponse"]["properties"]["providers"]
            assert "maxItems" not in listing
            assert listing["items"] == {"$ref": "#/components/schemas/ProviderSummary"}
            assert document["components"]["parameters"]["ProviderId"]["schema"]["enum"] == [
                "openai", "anthropic", "openrouter"
            ]
