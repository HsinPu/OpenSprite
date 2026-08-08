from opensprite.modules.documents.learning import LearningLedger


def test_learning_ledger_records_and_ranks_relevant_entries():
    ledger = LearningLedger()
    ledger.record_learning(
        "telegram:room-1",
        kind="skill",
        target_id="pytest-helper",
        summary="Reusable pytest workflow for updating assertions and running focused tests.",
        source_run_id="run-1",
    )
    ledger.record_learning(
        "telegram:room-1",
        kind="memory",
        target_id="memory",
        summary="Updated session memory.",
        source_run_id="run-2",
    )

    entries = ledger.relevant_entries("telegram:room-1", "Please update pytest assertions")

    assert entries
    assert entries[0]["kind"] == "skill"
    assert entries[0]["target_id"] == "pytest-helper"
    context = ledger.build_relevant_context(
        "telegram:room-1",
        "Please update pytest assertions",
    )
    assert "# Relevant Learned Context" in context
    assert "pytest-helper" in context
