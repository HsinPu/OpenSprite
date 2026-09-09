from contextlib import closing
import sqlite3
from uuid import uuid4

import pytest

from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.custom_agents.child_repository import ChildExecutionRepository
from opensprite_backend.custom_agents.models import AgentError


@pytest.fixture
def stores(tmp_path):
    database = tmp_path / "chat.sqlite"
    chats = SqliteConversationRepository(database)
    parent = chats.start_run(conversation_id=None, client_request_id=str(uuid4()),
                             message="parent", provider_id="openai", model_id="test",
                             response_mode="default").run
    chats.mark_run_started(parent.id)
    return ChildExecutionRepository(database), chats, parent, database


def create(repository, parent, call="call", **overrides):
    arguments = dict(parent_id=parent.id, call_id=call, request_hash="a" * 64,
                     agent_id=str(uuid4()), name="reviewer", revision=1,
                     definition_hash="b" * 64, provider_id="openai", model_id="test")
    arguments.update(overrides)
    return repository.create(**arguments)


def test_child_replay_is_durable_and_does_not_create_messages(stores):
    repository, chats, parent, database = stores
    first, replay = create(repository, parent)
    assert not replay
    restarted = ChildExecutionRepository(database)
    second, replay = create(restarted, parent)
    assert replay and first == second
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    with pytest.raises(AgentError, match="idempotency_conflict"):
        create(repository, parent, request_hash="c" * 64)


def test_child_ownership_and_terminal_state_cannot_be_overwritten(stores):
    repository, _, parent, _ = stores
    child, _ = create(repository, parent)
    with pytest.raises(AgentError, match="not_found"):
        repository.get(str(uuid4()), child.id)
    with pytest.raises(AgentError, match="not_found"):
        repository.transition(str(uuid4()), child.id, "running")
    repository.transition(parent.id, child.id, "running")
    done = repository.transition(parent.id, child.id, "completed", result_text="answer")
    assert done.result_text == "answer" and done.finished_at
    assert repository.transition(parent.id, child.id, "cancelled") == done


def test_parent_total_limit_and_restart_interrupt(stores):
    repository, _, parent, _ = stores
    children = [create(repository, parent, str(number))[0] for number in range(6)]
    repository.transition(parent.id, children[0].id, "running")
    repository.transition(parent.id, children[1].id, "cancelling")
    with pytest.raises(AgentError, match="child_limit_reached"):
        create(repository, parent, "seventh")
    assert repository.interrupt_incomplete() == 6
    assert repository.interrupt_incomplete() == 0
    assert all(child.status == "interrupted" for child in repository.list(parent.id))


def test_no_new_child_after_parent_cancellation(stores):
    repository, chats, parent, _ = stores
    chats.request_cancel(parent.id)
    with pytest.raises(AgentError, match="parent_not_running"):
        create(repository, parent)


def test_missing_database_does_not_create_file(tmp_path):
    file = tmp_path / "missing.sqlite"
    repository = ChildExecutionRepository(file)
    with pytest.raises(AgentError, match="store_unavailable"):
        repository.list(str(uuid4()))
    assert not file.exists()


def test_timeout_is_distinct_from_executor_cancellation(stores):
    repository, _, parent, _ = stores
    child, _ = create(repository, parent)
    repository.transition(parent.id, child.id, "running")
    repository.transition(parent.id, child.id, "cancelled")
    timed_out = repository.mark_timeout(parent.id, child.id)
    assert timed_out.status == "timed_out" and timed_out.error_code == "timeout"
    second, _ = create(repository, parent, "second")
    repository.transition(parent.id, second.id, "running")
    repository.transition(parent.id, second.id, "completed", result_text="completed first")
    assert repository.mark_timeout(parent.id, second.id).status == "completed"
