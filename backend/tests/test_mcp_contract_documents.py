"""Static checks for MCP connection and Tool approval contracts."""

from __future__ import annotations

import json
from pathlib import Path

from opensprite_backend.app import create_app


ROOT = Path(__file__).resolve().parents[2] / "contracts"


def load(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_mcp_contract_has_stdio_and_streamable_http_with_exact_operations() -> None:
    contract = load("mcp-connections.openapi.json")
    assert contract["openapi"] == "3.1.0"
    operations = {
        value["operationId"]
        for path in contract["paths"].values()  # type: ignore[union-attr]
        for method, value in path.items()  # type: ignore[union-attr]
        if method in {"get", "post", "put", "delete"}
    }
    assert operations == {
        "listMcpServers", "createMcpServer", "getMcpServer", "putMcpServer",
        "deleteMcpServer", "testMcpServer", "startMcpServer", "stopMcpServer",
        "listMcpTools",
    }
    text = json.dumps(contract, sort_keys=True).lower()
    assert '"const": "stdio"' in text
    assert '"const": "streamable-http"' in text
    assert '"const": "none"' in text
    assert '"const": "bearer-token"' in text
    assert '"discriminator"' in text
    assert '"oauth2"' not in text
    assert "apikey" not in text
    bearer = contract["components"]["schemas"]["BearerAuthenticationCreate"]  # type: ignore[index]
    assert bearer["properties"]["token"]["writeOnly"] is True
    assert "token" not in contract["components"]["schemas"]["McpServerSummary"]["properties"]  # type: ignore[index]


def test_approval_contract_has_only_allow_once_and_deny() -> None:
    contract = load("tool-approvals.openapi.json")
    path = contract["paths"]["/api/tool-approvals/{approval_id}"]  # type: ignore[index]
    assert path["get"]["operationId"] == "getToolApproval"
    assert path["put"]["operationId"] == "putToolApprovalDecision"
    decision = path["put"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["decision"]  # type: ignore[index]
    assert decision["enum"] == ["allow_once", "deny"]
    assert "always_allow" not in json.dumps(contract)


def test_generated_mcp_and_approval_operation_ids_match_documents() -> None:
    generated = create_app().openapi()
    assert generated["paths"]["/api/mcp/servers"]["post"]["operationId"] == "createMcpServer"
    assert generated["paths"]["/api/mcp/servers/{server_id}/tools"]["get"]["operationId"] == "listMcpTools"
    assert generated["paths"]["/api/tool-approvals/{approval_id}"]["put"]["operationId"] == "putToolApprovalDecision"
