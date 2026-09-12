"""Strict semantic attempt metadata; never provider payloads."""

from uuid import UUID
from .context_receipts import valid_context_receipt


def valid_attempt_payload(data: dict[str, object]) -> bool:
    common = {"schemaVersion", "requestId", "attemptId", "attemptNumber", "purpose",
              "retryOfAttemptId", "retryCause", "compactionId", "parentRequestId", "status"}
    extra = {"started": set(), "completed": {"finishReason", "inputTokens", "outputTokens"},
             "failed": {"errorCode"}, "cancelled": set()}.get(str(data.get("status")))
    if data.get("status") == "started" and "context" in data:
        if not valid_context_receipt(data["context"]):
            return False
        extra = {"context"}
    if extra is None or set(data) != common | extra or type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1:
        return False
    for key in ("requestId", "attemptId", "retryOfAttemptId", "compactionId", "parentRequestId"):
        value = data.get(key)
        if value is None and key not in {"requestId", "attemptId"}:
            continue
        try:
            if not isinstance(value, str) or str(UUID(value)) != value:
                return False
        except ValueError:
            return False
    if type(data["attemptNumber"]) is not int or not 1 <= data["attemptNumber"] <= 64:
        return False
    if data["purpose"] not in ("main", "continuation", "compaction") or data["retryCause"] not in (None, "provider_context_limit"):
        return False
    if (data["attemptNumber"] == 1) != (data["retryOfAttemptId"] is None) or (data["retryOfAttemptId"] is None) != (data["retryCause"] is None):
        return False
    if data["status"] == "completed":
        return data["finishReason"] in ("final", "tool_calls", "output_limit") and all(
            data[key] is None or (type(data[key]) is int and 0 <= data[key] <= 2**53 - 1)
            for key in ("inputTokens", "outputTokens"))
    if data["status"] == "failed":
        return data["errorCode"] in ("provider_not_connected", "invalid_credentials", "provider_rate_limited",
            "provider_timeout", "provider_unreachable", "context_limit_exceeded", "credential_store_unavailable",
            "invalid_provider_response", "internal_error")
    return True
