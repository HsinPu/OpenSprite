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
from opensprite_backend.schedules.models import ExecutionProfile
from opensprite_backend.workspaces import DEFAULT_WORKSPACE_ID


def selected_profile(repository, run_id):
    return next(item.data for item in repository.list_run_events(run_id, after_sequence=0, limit=200)
                if item.type is RunEventType.EXECUTION_SELECTED)


def test_setting_change_affects_next_run_and_replay_does_not_read_current_settings(tmp_path):
    chat, repository, manager, _ = service(tmp_path)
    paths = build_app_paths(tmp_path / ".opensprite")
    catalog = ExecutionPluginCatalog(())
    settings = ExecutionSettingsService(paths, catalog)
    chat._execution_settings = settings
    chat._execution_plugins = catalog

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
        manager._loop._gateway = gateway
        request_id = str(uuid4())
        try:
            first = await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                                        client_request_id=request_id, message="first request")
            await asyncio.wait_for(started.wait(), 5)
            await settings.update("standard", "no_recovery")
            release.set()
            first_result = await asyncio.wait_for(manager.wait(first.run.id), 5)
            assert first_result.status is RunStatus.COMPLETED
            assert first_result.completion_reason is CompletionReason.STOP
            assert first_result.partial_text == "accepted before change continued by pinned standard policy"
            assert selected_profile(repository, first.run.id)["policyId"] == "standard"

            second = await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                                         client_request_id=str(uuid4()), message="next request")
            second_result = await asyncio.wait_for(manager.wait(second.run.id), 5)
            assert second_result.status is RunStatus.COMPLETED
            assert second_result.completion_reason is CompletionReason.OUTPUT_LIMIT
            assert second_result.partial_text == "next run stops at output limit"
            assert selected_profile(repository, second.run.id)["policyId"] == "no_recovery"
            assert len(gateway.requests) == 3

            # A corrupt current settings file must not break an already accepted
            # idempotent replay, create another execution or change its profile.
            paths.execution_settings_file.write_text("invalid current settings", encoding="utf-8")
            replay = await chat.start_run(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                                         client_request_id=request_id, message="first request")
            assert replay.replayed and replay.run.id == first.run.id
            assert selected_profile(repository, replay.run.id)["policyId"] == "standard"
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
        '{"version":1,"loopId":"broken","policyId":"standard"}', encoding="utf-8")
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


@pytest.mark.parametrize("policy,request_count,reason", [
    ("standard", 2, CompletionReason.STOP),
    ("no_recovery", 1, CompletionReason.OUTPUT_LIMIT),
])
def test_scheduled_acceptance_uses_selected_plugins_and_replays_without_settings(
    tmp_path, policy, request_count, reason,
):
    chat, repository, manager, _ = service(tmp_path)
    paths = build_app_paths(tmp_path / ".opensprite")
    catalog = ExecutionPluginCatalog(())
    settings = ExecutionSettingsService(paths, catalog)
    chat._execution_settings = settings
    chat._execution_plugins = catalog

    class Gateway:
        requests = 0

        async def stream(self, request, *, attempt=None):
            self.requests += 1
            yield ModelTextDelta("scheduled partial" if self.requests == 1 else " continuation")
            yield ModelCompleted(ModelFinishReason.OUTPUT_LIMIT if self.requests == 1 else ModelFinishReason.FINAL)

    async def scenario():
        gateway = Gateway()
        manager._loop._gateway = gateway
        occurrence_id = str(uuid4())
        arguments = dict(conversation_id=None, workspace_id=DEFAULT_WORKSPACE_ID,
                         occurrence_id=occurrence_id, message="scheduled execution",
                         profile=ExecutionProfile("openrouter", "openrouter/auto", "balanced", "auto", "auto", "5"))
        try:
            await settings.update("standard", policy)
            accepted = await chat.start_scheduled_run(**arguments)
            result = await asyncio.wait_for(manager.wait(accepted.run.id), 5)
            assert result.status is RunStatus.COMPLETED
            assert result.source == "schedule"
            assert result.completion_reason is reason
            assert selected_profile(repository, result.id)["policyId"] == policy
            assert gateway.requests == request_count

            paths.execution_settings_file.write_text("invalid current settings", encoding="utf-8")
            replay = await chat.start_scheduled_run(**arguments)
            assert replay.replayed and replay.run.id == accepted.run.id
            assert gateway.requests == request_count
        finally:
            await chat.close()

    asyncio.run(scenario())
