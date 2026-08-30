"""Static checks for the authoritative conversation and run contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "agent-chat.openapi.json"
)


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_is_openapi_31_json() -> None:
    contract = load_contract()

    assert contract["openapi"] == "3.1.0"
    assert contract["info"]["version"] == "0.1.0-draft"
    assert contract["security"] == []


def test_contract_has_only_the_approved_agent_chat_operations() -> None:
    contract = load_contract()
    operations = {
        (path, method)
        for path, path_item in contract["paths"].items()
        for method in path_item
        if method in {"get", "put", "post", "delete", "patch"}
    }

    assert operations == {
        ("/api/conversations", "get"),
        ("/api/conversations/{conversation_id}/messages", "get"),
        ("/api/runs", "post"),
        ("/api/runs/{run_id}", "get"),
        ("/api/runs/{run_id}/events", "get"),
        ("/api/runs/{run_id}/cancel", "post"),
    }


def test_start_run_request_is_strict_and_idempotent() -> None:
    schema = load_contract()["components"]["schemas"]["StartRunRequest"]

    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "conversationId",
        "clientRequestId",
        "message",
    ]
    assert schema["properties"]["conversationId"]["oneOf"][0]["$ref"].endswith(
        "/Identifier"
    )
    assert schema["properties"]["conversationId"]["oneOf"][1] == {
        "type": "null"
    }
    assert schema["properties"]["clientRequestId"]["$ref"].endswith(
        "/Identifier"
    )
    assert schema["properties"]["message"]["minLength"] == 1
    assert schema["properties"]["message"]["maxLength"] == 32768


def test_run_snapshot_and_persisted_message_fields_are_fixed() -> None:
    schemas = load_contract()["components"]["schemas"]

    assert schemas["RunSnapshot"]["additionalProperties"] is False
    assert schemas["RunSnapshot"]["required"] == [
        "id",
        "conversationId",
        "userMessageId",
        "assistantMessageId",
        "providerId",
        "modelId",
        "responseMode",
        "status",
        "completionReason",
        "error",
        "partialText",
        "createdAt",
        "startedAt",
        "finishedAt",
    ]
    assert schemas["RunStatus"]["enum"] == [
        "queued",
        "running",
        "cancelling",
        "completed",
        "failed",
        "cancelled",
        "interrupted",
    ]
    assert schemas["CompletionReason"]["enum"] == ["stop", "output_limit", "context_limit"]
    assert schemas["RunSnapshot"]["properties"]["completionReason"]["oneOf"][0]["$ref"].endswith("/CompletionReason")
    assert schemas["Message"]["additionalProperties"] is False
    assert schemas["Message"]["required"] == [
        "id",
        "conversationId",
        "runId",
        "role",
        "content",
        "sequence",
        "createdAt",
    ]
    assert schemas["MessageRole"]["enum"] == ["user", "assistant"]


def test_public_run_events_are_semantic_and_do_not_expose_reasoning() -> None:
    schemas = load_contract()["components"]["schemas"]
    event_types = schemas["RunEventType"]["enum"]

    assert event_types == [
        "run.started",
        "context.compaction.started",
        "model.started",
        "response.continuation.started",
        "assistant.delta",
        "tool.started",
        "tool.completed",
        "tool.failed",
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.interrupted",
    ]
    assert not any(
        term in json.dumps(schemas["RunEvent"], sort_keys=True).lower()
        for term in ("chain_of_thought", "chainofthought", "reasoning_content")
    )
    assert schemas["RunCompletedEventData"]["required"] == [
        "assistantMessageId",
        "completionReason",
    ]
    assert schemas["ModelStartedEventData"]["required"] == [
        "providerId",
        "modelId",
        "responseMode",
        "maxOutputTokens",
    ]
    stream = load_contract()["paths"]["/api/runs/{run_id}/events"]["get"]
    assert "Last-Event-ID" in {
        parameter["name"]
        for parameter in stream["parameters"]
        if "name" in parameter
    }
    assert "text/event-stream" in stream["responses"]["200"]["content"]


def test_response_mode_keeps_provider_default_as_an_explicit_value() -> None:
    schemas = load_contract()["components"]["schemas"]

    assert schemas["ProviderId"]["enum"] == [
        "openai",
        "anthropic",
        "openrouter",
    ]
    assert schemas["ResponseMode"]["enum"] == [
        "default",
        "fast",
        "balanced",
        "deep",
    ]


def test_http_error_mapping_is_explicit() -> None:
    paths = load_contract()["paths"]
    start = paths["/api/runs"]["post"]["responses"]
    cancel = paths["/api/runs/{run_id}/cancel"]["post"]["responses"]

    assert start["400"]["$ref"].endswith("/InvalidRequest")
    assert start["409"]["$ref"].endswith("/RunStartConflict")
    assert start["503"]["$ref"].endswith("/LocalStoreUnavailable")
    assert start["500"]["$ref"].endswith("/InternalError")
    assert cancel["404"]["$ref"].endswith("/NotFound")
    assert cancel["409"]["$ref"].endswith("/RunNotActive")
    assert cancel["503"]["$ref"].endswith("/LocalStoreUnavailable")
    assert cancel["500"]["$ref"].endswith("/InternalError")
