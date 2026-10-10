"""Faults in optional recording never replace durable execution guarantees."""
import asyncio
import logging
from threading import Event
from uuid import uuid4

import pytest

from context_test_support import TestCapabilityResolver
from test_agent_loop import ScriptedGateway
from opensprite_backend.application.run_preparation import ProductRunExecutor
from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.conversations.models import RunStatus
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.inference.models import ModelCompleted, ModelFinishReason, ModelTextDelta
from opensprite_backend.models import GeneralSettings
from opensprite_backend.prompt_logging import FilePromptLogWriter, PromptRecorder
from opensprite_backend.system_prompt import FileSystemPromptLogWriter, create_system_prompt_provider
from test_system_prompt import StubGeneralSettings, fixed_clock, rendered_prompt


@pytest.mark.parametrize("enabled", [False, True])
def test_product_recording_choice_controls_both_receipts(tmp_path, enabled):
    async def exercise():
        paths = build_app_paths(tmp_path / ".opensprite")
        repository = SqliteConversationRepository(paths.database_file)
        run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message=str(uuid4()),
            provider_id="openrouter", model_id="openrouter/auto", response_mode="default", log_full_prompts=enabled).run
        recorder = PromptRecorder(FileSystemPromptLogWriter(paths), FilePromptLogWriter(paths))
        gateway = ScriptedGateway([[ModelTextDelta("result"), ModelCompleted(ModelFinishReason.FINAL)]])
        executor = ProductRunExecutor(repository=repository, gateway=gateway, capability_resolver=TestCapabilityResolver(),
            system_prompt_provider=create_system_prompt_provider(StubGeneralSettings(GeneralSettings(locale="en", timeZone="UTC")), recorder, clock=fixed_clock),
            request_observer=recorder)
        result = await executor.execute(run.id, asyncio.Event())
        await recorder.aclose()
        assert result.status is RunStatus.COMPLETED
        assert len(gateway.requests) == 1
        assert len(list(paths.system_prompt_logs_dir.rglob("*.md"))) == int(enabled)
        assert len(list(paths.prompt_logs_dir.rglob("*.md"))) == int(enabled)
        if enabled:
            system_receipt = next(paths.system_prompt_logs_dir.rglob("*.md")).read_text(encoding="utf-8")
            base_prompt = system_receipt.split("## Rendered System Prompt\n\n", 1)[1].rstrip("\n")
            assert gateway.requests[0].messages[0].content.startswith(base_prompt)
            request_receipt = next(paths.prompt_logs_dir.rglob("*.md")).read_text(encoding="utf-8")
            assert gateway.requests[0].messages[0].content in request_receipt
        else:
            assert not paths.system_prompt_logs_dir.exists()
            assert not paths.prompt_logs_dir.exists()
        assert repository.get_run(run.id).status is RunStatus.COMPLETED
    asyncio.run(exercise())


def test_failed_and_blocked_recording_does_not_block_inference(tmp_path, caplog):
    entered, release = Event(), Event()
    class BlockedWriter:
        def write(self, **kwargs):
            entered.set()
            release.wait(5)
            raise OSError("secret-disk-error")
    async def exercise():
        paths = build_app_paths(tmp_path / ".opensprite")
        repository = SqliteConversationRepository(paths.database_file)
        run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message="private-input",
            provider_id="openrouter", model_id="openrouter/auto", response_mode="default", log_full_prompts=True).run
        recorder = PromptRecorder(BlockedWriter(), BlockedWriter(), capacity=1)
        gateway = ScriptedGateway([[ModelTextDelta("result"), ModelCompleted(ModelFinishReason.FINAL)]])
        executor = ProductRunExecutor(repository=repository, gateway=gateway, capability_resolver=TestCapabilityResolver(),
            system_prompt_provider=create_system_prompt_provider(StubGeneralSettings(GeneralSettings(locale="en", timeZone="UTC")), recorder),
            request_observer=recorder, max_duration_seconds=1)
        try:
            result = await asyncio.wait_for(executor.execute(run.id, asyncio.Event()), timeout=2)
            assert result.status is RunStatus.COMPLETED
            assert len(gateway.requests) == 1
            assert entered.is_set()
            assert not await recorder.flush(timeout=.01)
        finally:
            release.set()
            await recorder.aclose()
    with caplog.at_level(logging.WARNING):
        asyncio.run(exercise())
    assert "prompt_recording_skipped" in caplog.text
    assert "prompt_recording_unavailable" in caplog.text
    assert "prompt_recording_flush_timeout" in caplog.text
    assert "secret-disk-error" not in caplog.text
    assert "private-input" not in caplog.text


def test_oversize_record_is_rejected_before_filesystem_io(tmp_path, caplog):
    from dataclasses import replace
    paths = build_app_paths(tmp_path / ".opensprite")
    recorder = PromptRecorder(FileSystemPromptLogWriter(paths), FilePromptLogWriter(paths))
    with caplog.at_level(logging.WARNING):
        recorder.record_system(run_id=str(uuid4()), prompt=replace(rendered_prompt(), content="x" * (8 * 1024 * 1024 + 1)))
        asyncio.run(recorder.aclose())
    assert "prompt_recording_skipped" in caplog.text
    assert not paths.home.exists()


def test_observer_failure_and_mutation_cannot_change_transmitted_inputs(tmp_path, caplog):
    class MutatingObserver:
        def record_request(self, *, request, **kwargs):
            object.__setattr__(request.messages[0], 'content', 'mutated-prefix')
            object.__setattr__(request, 'max_output_tokens', 1)
            raise RuntimeError('private-observer-detail')
    async def exercise():
        paths = build_app_paths(tmp_path / '.opensprite')
        repository = SqliteConversationRepository(paths.database_file)
        marker = str(uuid4())
        run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message=marker,
            provider_id='openrouter', model_id='openrouter/auto', response_mode='default', log_full_prompts=True).run
        gateway = ScriptedGateway([[ModelTextDelta(marker), ModelCompleted(ModelFinishReason.FINAL)]])
        executor = ProductRunExecutor(repository=repository, gateway=gateway, capability_resolver=TestCapabilityResolver(),
                                      request_observer=MutatingObserver())
        result = await executor.execute(run.id, asyncio.Event())
        assert result.status is RunStatus.COMPLETED
        assert gateway.requests[0].messages[0].content != 'mutated-prefix'
        assert gateway.requests[0].max_output_tokens > 1
        assert gateway.requests[0].messages[-1].content == marker
    with caplog.at_level(logging.WARNING):
        asyncio.run(exercise())
    assert 'request_observer_unavailable' in caplog.text
    assert 'private-observer-detail' not in caplog.text
