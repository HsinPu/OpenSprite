"""Bounded public step events; outputs are read separately from step storage."""
from uuid import UUID

STEP_ERROR_CODES = frozenset({"provider_not_connected", "invalid_credentials",
    "provider_rate_limited", "provider_timeout", "provider_unreachable",
    "context_limit_exceeded", "context_preparation_failed", "credential_store_unavailable",
    "invalid_provider_response", "internal_error", "agent_limit_reached"})


def valid_step_payload(event_type, data):
    try:
        if not isinstance(data.get("stepId"), str) or str(UUID(data["stepId"])) != data["stepId"]:
            return False
    except ValueError:
        return False
    if event_type == "step.started":
        return (set(data) == {"stepId", "sequence", "label", "channel"}
                and type(data["sequence"]) is int and 1 <= data["sequence"] <= 2048
                and isinstance(data["label"], str) and 1 <= len(data["label"]) <= 64
                and data["channel"] in {"draft", "answer"})
    return (event_type == "step.completed"
            and set(data) == {"stepId", "status", "finishReason", "errorCode", "inputTokens", "outputTokens"}
            and data["status"] in {"completed", "failed", "cancelled"}
            and data["finishReason"] in {None, "final", "output_limit"}
            and data["errorCode"] in (STEP_ERROR_CODES | {None})
            and all(value is None or type(value) is int and 0 <= value <= 2**53-1
                    for value in (data["inputTokens"], data["outputTokens"])))
