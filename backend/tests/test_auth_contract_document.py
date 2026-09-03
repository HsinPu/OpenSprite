import json
from pathlib import Path

from opensprite_backend.app import create_app


CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "local-authentication.openapi.json"


def test_auth_contract_has_exact_operations_and_write_only_secrets() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    operations = {
        item["operationId"]
        for path in contract["paths"].values()
        for method, item in path.items()
        if method in {"get", "post", "put"}
    }
    assert operations == {"getAuthStatus", "setupLocalAccess", "loginLocalAccess", "logoutLocalAccess", "logoutAllLocalAccess", "changeLocalPassword"}
    schemas = contract["components"]["schemas"]
    for schema_name in ("SetupRequest", "LoginRequest", "PasswordChangeRequest"):
        assert schemas[schema_name]["additionalProperties"] is False
        assert all(item.get("writeOnly") for item in schemas[schema_name]["properties"].values())


def test_generated_auth_operation_ids_match_document() -> None:
    generated = create_app().openapi()
    assert generated["paths"]["/api/auth/status"]["get"]["operationId"] == "getAuthStatus"
    assert generated["paths"]["/api/auth/password"]["put"]["operationId"] == "changeLocalPassword"
