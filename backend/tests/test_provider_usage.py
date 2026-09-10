"""Deletion guards count live references without preventing historical display."""

from uuid import uuid4

from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository


def test_provider_usage_counts_active_runs_but_not_history(tmp_path):
    repository = SqliteConversationRepository(tmp_path / "chat.sqlite")
    identifier = str(uuid4())
    assert repository.provider_usage(identifier) == (0, 0)
    repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message="hello",
        provider_id=identifier, model_id="local", response_mode="default")
    assert repository.provider_usage(identifier) == (1, 0)
    assert repository.provider_usage(identifier, "local") == (1, 0)
    assert repository.provider_usage(identifier, "other") == (0, 0)
    assert repository.provider_usage(str(uuid4())) == (0, 0)
    repository.interrupt_incomplete_runs()
    assert repository.provider_usage(identifier) == (0, 0)
