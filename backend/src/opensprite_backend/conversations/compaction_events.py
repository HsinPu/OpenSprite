"""Content-free diagnostic payload validation for compaction operations."""

from uuid import UUID


def valid_compaction_payload(event_type: str, data: dict[str, object]) -> bool:
    """Accept old starts or a bounded, versioned lifecycle receipt."""
    if event_type == "context.compaction.started" and not data:
        return True
    common = {"schemaVersion", "compactionId"}
    fields = {
        "context.compaction.started": {"reason", "fromSequence", "throughSequence", "estimatedBeforeTokens", "inputBudgetTokens"},
        "context.compaction.completed": {"throughSequence", "inputTokens", "outputTokens"},
        "context.compaction.failed": {"errorCode"},
        "context.compaction.cancelled": {"reason"},
    }
    expected = fields.get(event_type)
    if expected is None or set(data) != common | expected:
        return False
    if type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1:
        return False
    identifier = data["compactionId"]
    if not isinstance(identifier, str):
        return False
    try:
        if str(UUID(identifier)) != identifier:
            return False
    except ValueError:
        return False
    for key in expected - {"reason", "errorCode"}:
        if type(data[key]) is not int or not 0 <= data[key] <= 2**53 - 1:
            return False
    if event_type.endswith("started"):
        return (
            data["reason"] in ("local_budget", "provider_context_limit")
            and 1 <= data["fromSequence"] <= data["throughSequence"]
            and data["inputBudgetTokens"] > 0
        )
    if event_type.endswith("failed"):
        return data["errorCode"] in ("context_limit", "preparation_failed", "provider_failed")
    if event_type.endswith("cancelled"):
        return data["reason"] == "cancelled"
    return data["throughSequence"] > 0
