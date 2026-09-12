from opensprite_backend.conversations.compaction_events import valid_compaction_payload


BASE = {"schemaVersion": 1, "compactionId": "11111111-1111-4111-8111-111111111111"}


def test_legacy_start_remains_readable():
    assert valid_compaction_payload("context.compaction.started", {})
    assert not valid_compaction_payload("context.compaction.completed", {})


def test_lifecycle_payloads():
    for kind, payload in {
        "started": {"reason": "local_budget", "fromSequence": 1, "throughSequence": 4, "estimatedBeforeTokens": 500, "inputBudgetTokens": 400},
        "completed": {"throughSequence": 4, "inputTokens": 300, "outputTokens": 50},
        "failed": {"errorCode": "provider_failed"},
        "cancelled": {"reason": "cancelled"},
    }.items():
        assert valid_compaction_payload(f"context.compaction.{kind}", BASE | payload)
        assert not valid_compaction_payload(f"context.compaction.{kind}", BASE | payload | {"prompt": "private"})


def test_rejects_invalid_identity_and_boolean_numbers():
    payload = BASE | {"throughSequence": 4, "inputTokens": 300, "outputTokens": 50}
    for replacement in ({"compactionId": "bad"}, {"schemaVersion": True}, {"inputTokens": True}, {"outputTokens": -1}):
        assert not valid_compaction_payload("context.compaction.completed", payload | replacement)
