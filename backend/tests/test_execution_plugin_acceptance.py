"""Accepted executions retain their policy when settings change or replay."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from test_agent_chat_service import service
from test_execution_plugin_catalog import InstalledPoint, LOOPS

from opensprite_backend.agent.plugin_catalog import ExecutionPluginCatalog
from opensprite_backend.application import AgentChatError, ChatErrorCode
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import CompletionReason, RunEventType, RunStatus
from opensprite_backend.execution_settings import ExecutionSettingsService
from opensprite_backend.inference.models import ModelCompleted, ModelFinishReason, ModelTextDelta
from opensprite_backend.workspaces import DEFAULT_WORKSPACE_ID


def selected_profile(repository, run_id):
    return next(item.data for item in repository.list_run_events(run_id, after_sequence=0, limit=200)
                if item.type is RunEventType.EXECUTION_SELECTED)


def test_setting_change_affects_next_run_and_replay_does_not_read_current_settings(tmp_path):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        class Gateway:
            requests = []

            async def stream(self, request, *, attempt=None):
                self.requests.append(request)
                count = len(self.requests)
                if count == 1:
                    started.set()
                    await release.wait()
                    yield ModelTextDelta("accepted before change ")
                    yield ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)
                elif count == 2:
                    yield ModelTextDelta("continued by pinned standard policy")
                    yield ModelCompleted(ModelFinishReason.FINAL)
                elif count == 3:
                    yield ModelTextDelta("next run stops at output limit")
                    yield ModelCompleted(ModelFinishReason.OUTPUT_LIMIT)
                else:
                    raise AssertionError("The no_recovery policy continued output.")

        gateway = Gateway()
        chat, repository, manager, _ = service(tmp_path, gateway=gateway)
        paths = build_app_paths(tmp_path / ".opensprite")
        catalog = ExecutionPluginCatalog()
        settings = ExecutionSettingsService(paths, catalog)
        chat._execution_settings = settings
        chat._execution_plugins = catalog
        request_id = str(uuid4())
        try:
            first = await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                                        client_request_id=request_id, message="first request")
            await asyncio.wait_for(started.wait(), 5)
            await settings.update("no_recovery", 0)
            release.set()
            first_result = await asyncio.wait_for(manager.wait(first.run.id), 5)
            assert first_result.status is RunStatus.COMPLETED
            assert first_result.completion_reason is CompletionReason.STOP
            assert first_result.partial_text == "accepted before change continued by pinned standard policy"
            assert selected_profile(repository, first.run.id)["pluginId"] == "standard"

            second = await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                                         client_request_id=str(uuid4()), message="next request")
            second_result = await asyncio.wait_for(manager.wait(second.run.id), 5)
            assert second_result.status is RunStatus.COMPLETED
            assert second_result.completion_reason is CompletionReason.OUTPUT_LIMIT
            assert second_result.partial_text == "next run stops at output limit"
            assert selected_profile(repository, second.run.id)["pluginId"] == "no_recovery"
            assert len(gateway.requests) == 3

            # A corrupt current settings file must not break an already accepted
            # idempotent replay, create another execution or change its profile.
            paths.execution_settings_file.write_text("invalid current settings", encoding="utf-8")
            replay = await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                                         client_request_id=request_id, message="first request")
            assert replay.replayed and replay.run.id == first.run.id
            assert selected_profile(repository, replay.run.id)["pluginId"] == "standard"
            assert len(gateway.requests) == 3
        finally:
            release.set()
            await chat.close()

    asyncio.run(scenario())


def test_unavailable_selected_plugin_fails_before_persisting_user_message(tmp_path):
    chat, repository, manager, _ = service(tmp_path)
    paths = build_app_paths(tmp_path / ".opensprite")
    point = InstalledPoint("broken", LOOPS, RuntimeError("private failed import"))
    catalog = ExecutionPluginCatalog((point,))
    settings = ExecutionSettingsService(paths, catalog)
    paths.execution_settings_file.parent.mkdir(parents=True, exist_ok=True)
    paths.execution_settings_file.write_text(
        '{"version":2,"revision":1,"pluginId":"broken"}', encoding="utf-8")
    chat._execution_settings = settings
    chat._execution_plugins = catalog

    async def scenario():
        try:
            with pytest.raises(AgentChatError) as failure:
                await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                                     client_request_id=str(uuid4()), message="must not persist")
            assert failure.value.code is ChatErrorCode.SETTINGS_STORE_UNAVAILABLE
            assert "private failed import" not in str(failure.value)
            assert not paths.database_file.exists()
            assert point.loads == 1
            assert manager._tasks == {}
        finally:
            await chat.close()

    asyncio.run(scenario())
