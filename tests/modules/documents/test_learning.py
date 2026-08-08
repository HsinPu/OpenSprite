from opensprite.modules.documents.learning import RelevantLearningContextService


class _RecordingLearningSource:
    def __init__(self, context: str):
        self.context = context
        self.calls: list[tuple[str, str]] = []

    def build_relevant_context(self, session_id: str, current_message: str) -> str:
        self.calls.append((session_id, current_message))
        return self.context


def test_relevant_learning_context_is_empty_without_attached_source():
    service = RelevantLearningContextService()

    assert service.build_context("telegram:room-1", "pytest assertions") == ""


def test_relevant_learning_context_delegates_to_attached_source():
    source = _RecordingLearningSource("# Relevant Learned Context\n\n- pytest-helper")
    service = RelevantLearningContextService()

    service.set_learning_ledger(source)
    context = service.build_context("telegram:room-1", "pytest assertions")

    assert context == source.context
    assert source.calls == [("telegram:room-1", "pytest assertions")]


def test_relevant_learning_context_can_clear_attached_source():
    source = _RecordingLearningSource("# Relevant Learned Context")
    service = RelevantLearningContextService(source)

    assert service.build_context("telegram:room-1", "pytest assertions") == source.context
    assert source.calls == [("telegram:room-1", "pytest assertions")]

    service.set_learning_ledger(None)

    assert service.build_context("telegram:room-1", "pytest assertions") == ""
    assert source.calls == [("telegram:room-1", "pytest assertions")]
