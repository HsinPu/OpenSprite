"""Agent-loop storage port for a child: isolated task history, durable events.

The conversation identity here is a private in-memory transcript identity, not
an entry in the conversations table. No parent messages are read or modified.
"""

from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from opensprite_backend.conversations.models import (
    CompletedRun, CompletionReason, Message, MessagePage, RunEvent, RunEventType,
    RunSnapshot, RunStatus, StoreFailure,
)
from opensprite_backend.conversations.repository import ConversationStoreError
from .child_repository import ChildExecution, ChildExecutionRepository
from .models import AgentError


class ChildContextRepository:
    def __init__(self, store: ChildExecutionRepository, child: ChildExecution,
                 parent: RunSnapshot, task: str) -> None:
        self._store = store
        self._parent_id = parent.id
        self._lock = RLock()
        now = datetime.now(UTC)
        message_id = str(uuid4())
        self._run = replace(
            parent, reasoning_resolution=None, id=child.id, conversation_id=child.id,
            user_message_id=message_id, assistant_message_id=None,
            provider_id=child.provider_id, model_id=child.model_id,
            status=RunStatus.QUEUED, partial_text="", error=None,
            created_at=now, started_at=None, finished_at=None, completion_reason=None,
        )
        self._message = Message(message_id, child.id, child.id, "user", task, 1, now)

    def _require(self, identifier: str) -> None:
        if identifier != self._run.id:
            raise ConversationStoreError(StoreFailure.NOT_FOUND)

    def _persist(self, status: str, result: str = "", error: str | None = None):
        try:
            return self._store.transition(self._parent_id, self._run.id, status,
                                          result_text=result, error_code=error)
        except AgentError as exc:
            raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from exc

    def get_run(self, run_id):
        self._require(run_id)
        return self._run

    def list_messages(self, conversation_id, *, limit, before_sequence=None):
        self._require(conversation_id)
        items = (self._message,) if before_sequence is None or before_sequence > 1 else ()
        return MessagePage(items, None)

    def list_messages_after(self, conversation_id, *, after_sequence, limit):
        self._require(conversation_id)
        return (self._message,) if after_sequence < 1 else ()

    def get_latest_compaction(self, conversation_id):
        self._require(conversation_id)
        # Only the explicit delegation prompt is history; it must not be
        # compacted away to make an oversized mandatory task appear to fit.
        return None

    def set_reasoning_resolution(self, run_id, resolution):
        with self._lock:
            self._require(run_id)
            if self._run.response_mode != resolution.requested:
                raise ConversationStoreError(StoreFailure.INVALID_STATE)
            if self._run.reasoning_resolution is None:
                self._run = replace(self._run, reasoning_resolution=resolution)
            return self._run

    def mark_run_started(self, run_id, availability=None, mounts=()):
        with self._lock:
            self._require(run_id)
            persisted = self._persist("running")
            # A durable child may have been cancelled, timed out, interrupted,
            # or otherwise completed before the loop reaches its first
            # lifecycle callback.  The repository returns the terminal row
            # instead of raising for those races; never resurrect that row in
            # the in-memory child run.
            if persisted.status != "running":
                raise ConversationStoreError(StoreFailure.RUN_NOT_ACTIVE)
            self._run = replace(self._run, status=RunStatus.RUNNING, started_at=datetime.now(UTC))
            return self._run

    def append_run_event(self, run_id, event_type, data):
        with self._lock:
            self._require(run_id)
            try:
                sequence = self._store.append_event(self._parent_id, run_id, event_type.value, data)
            except AgentError as exc:
                raise ConversationStoreError(StoreFailure.DATABASE_UNAVAILABLE) from exc
            return RunEvent(sequence, event_type, run_id, run_id, datetime.now(UTC), data)

    def append_assistant_delta(self, run_id, text):
        with self._lock:
            self._require(run_id)
            combined = self._run.partial_text + text
            if len(combined) > 1048576:
                raise ConversationStoreError(StoreFailure.INVALID_REQUEST)
            event = self.append_run_event(run_id, RunEventType.ASSISTANT_DELTA, {"text": text})
            self._run = replace(self._run, partial_text=combined)
            return event

    def complete_run(self, run_id, text, completion_reason=CompletionReason.STOP):
        with self._lock:
            self._require(run_id)
            self._persist("completed", text)
            message = Message(str(uuid4()), run_id, run_id, "assistant", text, 2, datetime.now(UTC))
            self._run = replace(self._run, status=RunStatus.COMPLETED, partial_text=text,
                                assistant_message_id=message.id, finished_at=message.created_at,
                                completion_reason=completion_reason)
            return CompletedRun(self._run, message)

    def fail_run(self, run_id, error):
        with self._lock:
            self._require(run_id)
            self._persist("failed", self._run.partial_text, error.code)
            self._run = replace(self._run, status=RunStatus.FAILED, error=error, finished_at=datetime.now(UTC))
            return self._run

    def request_cancel(self, run_id):
        with self._lock:
            self._require(run_id)
            if self._run.status in {RunStatus.QUEUED, RunStatus.RUNNING}:
                self._persist("cancelling", self._run.partial_text)
                self._run = replace(self._run, status=RunStatus.CANCELLING)
            return self._run

    def mark_run_cancelled(self, run_id):
        with self._lock:
            self._require(run_id)
            self._persist("cancelled", self._run.partial_text)
            self._run = replace(self._run, status=RunStatus.CANCELLED, finished_at=datetime.now(UTC))
            return self._run
