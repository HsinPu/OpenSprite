"""Run-local unified behavior, admission durability and inert API v2 history."""

import asyncio
import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest
from context_test_support import TestCapabilityResolver
from test_agent_loop import ScriptedGateway, accepted_run, store
from test_agent_chat_service import service
from opensprite_backend.application.run_preparation import ProductRunExecutor
from opensprite_backend.execution_plugins.catalog import ExecutionPluginCatalog
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.application import AgentChatError
from opensprite_backend.conversations.models import CompletionReason, RunEventType, RunStatus
from opensprite_backend.conversations.repository import ConversationStoreError
from opensprite_backend.execution_settings import ExecutionSettingsService
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.inference.models import InferenceFailure, ModelCompleted, ModelFinishReason, ModelTextDelta
from opensprite_backend.workspaces.models import DEFAULT_WORKSPACE_ID


def test_profile_is_persisted_with_queued_admission_and_replay_does_not_replace_it(tmp_path):
    repository = store(tmp_path)
    arguments = dict(conversation_id=None, client_request_id=str(uuid4()), message=str(uuid4()), provider_id="openai", model_id="test", response_mode="default")
    profile = ExecutionPluginCatalog().resolve("standard").profile()
    first = repository.start_run(**arguments, execution_profile=profile)
    assert first.run.status is RunStatus.QUEUED
    events = repository.list_run_events(first.run.id, after_sequence=0, limit=100)
    assert len(events) == 1 and events[0].data == profile
    replay = repository.start_run(**arguments, execution_profile=ExecutionPluginCatalog().resolve("no_recovery").profile())
    assert replay.replayed and replay.run.id == first.run.id
    assert repository.list_run_events(first.run.id, after_sequence=0, limit=100) == events


def test_invalid_profile_rolls_back_message_and_run_in_same_transaction(tmp_path):
    repository = store(tmp_path)
    with pytest.raises(ConversationStoreError):
        repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message="must roll back", provider_id="openai", model_id="test", response_mode="default", execution_profile={"pluginId":"../x", "pluginVersion":"3", "apiVersion":3})
    assert repository.list_conversations(limit=100, before=None).items == ()


def test_api_v2_profile_rows_are_readable_without_rewriting_or_loading(tmp_path):
    repository = store(tmp_path)
    run = accepted_run(repository)
    old = {"loopId":"old_loop", "loopVersion":"0.2.0", "policyId":"old_policy", "policyVersion":"0.2.0", "apiVersion":2}
    repository.mark_run_started(run.id)
    repository.append_run_event(run.id, RunEventType.EXECUTION_SELECTED, old)
    database = build_app_paths(tmp_path / ".opensprite").database_file
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT payload_json FROM run_events WHERE run_id=? AND type='execution.selected'", (run.id,)).fetchone()[0]
    event = next(e for e in repository.list_run_events(run.id, after_sequence=0, limit=100) if e.type is RunEventType.EXECUTION_SELECTED)
    assert event.data == old
    assert next(e for e in repository.list_run_events(run.id, after_sequence=0, limit=100) if e.type is RunEventType.EXECUTION_SELECTED) == event
    with sqlite3.connect(database) as connection:
        after = connection.execute("SELECT payload_json FROM run_events WHERE run_id=? AND type='execution.selected'", (run.id,)).fetchone()[0]
    assert after == before and json.loads(after) == old


def test_legacy_external_choice_blocks_new_admission_without_persisting(tmp_path):
    chat, repository, manager, _ = service(tmp_path)
    paths = build_app_paths(tmp_path / ".opensprite")
    paths.config_dir.mkdir(parents=True)
    original = b'{"version":1,"loopId":"external","policyId":"standard"}'
    paths.execution_settings_file.write_bytes(original)
    catalog = ExecutionPluginCatalog(())
    chat._execution_settings = ExecutionSettingsService(paths, catalog)
    chat._execution_plugins = catalog
    async def scenario():
        try:
            with pytest.raises(AgentChatError):
                await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID, client_request_id=str(uuid4()), message="must not persist")
            assert not paths.database_file.exists() and manager._tasks == {}
            assert paths.execution_settings_file.read_bytes() == original
        finally: await chat.close()
    asyncio.run(scenario())
