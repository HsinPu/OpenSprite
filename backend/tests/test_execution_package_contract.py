"""Authoritative package operations and identity semantics remain explicit."""

import json
from pathlib import Path


def test_package_contract_defines_only_import_inventory_remove_and_bundle():
    document = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "execution-plugin-packages.openapi.json").read_text())
    assert document["openapi"] == "3.1.0"
    assert set(document["paths"]) == {"/api/execution-plugin-packages", "/api/execution-plugin-packages/{package_id}",
                                      "/api/execution-plugin-packages/{package_id}/deployment-bundle"}
    post = document["paths"]["/api/execution-plugin-packages"]["post"]
    request = post["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert request["required"] == ["file"] and request["additionalProperties"] is False
    schemas = document["components"]["schemas"]
    assert schemas["PackageSummary"]["properties"]["runtimeStatus"]["enum"] == ["not_installed", "confirmed", "unverified", "mismatch", "needs_update"]
    assert schemas["PackageSummary"]["properties"]["sizeBytes"]["maximum"] == 10 * 1024 * 1024
    assert "same-origin" in str(document["x-transport-security"])
    assert "same ID/version" in document["x-deployment"] or "Same ID/version" in document["x-deployment"]
