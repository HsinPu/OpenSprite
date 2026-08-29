"""Authoritative Conversation Settings contract alignment."""

from __future__ import annotations

import json
from pathlib import Path

from opensprite_backend.app import create_app


CONTRACT_PATH = (
    Path(__file__).parents[2] / "contracts" / "conversation-settings.openapi.json"
)


def test_contract_and_generated_openapi_have_exact_conversation_shape() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    generated = create_app().openapi()
    contract_schema = contract["components"]["schemas"]["ConversationSettings"]
    generated_schema = generated["components"]["schemas"]["ConversationSettings"]

    assert contract["info"]["version"] == "0.2.0-draft"
    assert contract_schema["required"] == ["startupView", "sendBehavior", "autoScroll", "executionPanelDefaultExpanded"]
    assert generated_schema["required"] == contract_schema["required"]
    assert generated_schema["properties"]["startupView"]["enum"] == [
        "new",
        "recent",
    ]
    assert generated_schema["properties"]["sendBehavior"]["enum"] == [
        "enter",
        "modifier-enter",
    ]
    assert generated_schema["properties"]["autoScroll"] == {"type": "boolean", "title": "Autoscroll"}
    assert generated_schema["properties"]["executionPanelDefaultExpanded"]["type"] == "boolean"
    assert set(contract["paths"]) == {"/api/settings/conversation"}
    assert generated["paths"]["/api/settings/conversation"]["get"][
        "operationId"
    ] == "getConversationSettings"
    assert generated["paths"]["/api/settings/conversation"]["put"][
        "operationId"
    ] == "putConversationSettings"
