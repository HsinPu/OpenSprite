"""Local, content-free records of actual gateway attempts (not transport retries)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

from opensprite_backend.conversations.models import RunEventType
from opensprite_backend.conversations.repository import ConversationRepository, ConversationStoreError
from opensprite_backend.inference.gateway import ModelGateway, ModelGatewayError
from opensprite_backend.inference.models import ModelCompleted, ModelRequest, ModelUsage
from .context.receipt import ReceiptSources, request_receipt


@dataclass(frozen=True)
class Attempt:
    run_id: str
    request_id: str
    purpose: str
    number: int = 1
    retry_of: str | None = None
    cause: str | None = None
    compaction_id: str | None = None
    parent_request_id: str | None = None
    id: str = ""
    sources: ReceiptSources | None = None

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, "id", str(uuid4()))

    def payload(self, status: str) -> dict[str, object]:
        return {
            "schemaVersion": 1, "requestId": self.request_id,
            "attemptId": self.id, "attemptNumber": self.number,
            "purpose": self.purpose, "retryOfAttemptId": self.retry_of,
            "retryCause": self.cause, "compactionId": self.compaction_id,
            "parentRequestId": self.parent_request_id, "status": status,
        }


class TracedGateway:
    def __init__(self, gateway: ModelGateway, repository: ConversationRepository):
        self._gateway = gateway
        self._repository = repository
        self._scope: ContextVar[Attempt | None] = ContextVar("gateway_attempt", default=None)

    @contextmanager
    def scope(self, attempt: Attempt):
        token = self._scope.set(attempt)
        try:
            yield
        finally:
            self._scope.reset(token)

    async def _record(self, attempt: Attempt, status: str, **metadata: object):
        try:
            await asyncio.to_thread(
                self._repository.append_run_event, attempt.run_id,
                RunEventType.MODEL_ATTEMPT, {**attempt.payload(status), **metadata},
            )
        except ConversationStoreError:
            # Diagnostics must not replay a request or replace its original error.
            logging.getLogger("opensprite.agent.context").warning(
                "attempt diagnostics unavailable run_id=%s attempt_id=%s", attempt.run_id, attempt.id,
            )

    async def stream(self, request: ModelRequest, *, attempt: Attempt | None = None):
        attempt = attempt or self._scope.get()
        if attempt is None:
            async for event in self._gateway.stream(request):
                yield event
            return
        await self._record(attempt, "started", context=request_receipt(request, attempt.sources, attempt.purpose))
        terminal = False
        finish_reason = None
        input_tokens = output_tokens = None
        stream = self._gateway.stream(request)
        try:
            async for event in stream:
                if isinstance(event, ModelUsage):
                    input_tokens, output_tokens = event.input_tokens, event.output_tokens
                if isinstance(event, ModelCompleted):
                    finish_reason = event.reason.value
                yield event
            if not terminal:
                if finish_reason is None:
                    await self._record(attempt, "failed", errorCode="invalid_provider_response")
                else:
                    await self._record(attempt, "completed", finishReason=finish_reason,
                                       inputTokens=input_tokens, outputTokens=output_tokens)
                terminal = True
        except (asyncio.CancelledError, GeneratorExit):
            if not terminal:
                await self._record(attempt, "cancelled")
                terminal = True
            raise
        except Exception as error:
            if not terminal:
                await self._record(attempt, "failed", errorCode=error.failure.value if isinstance(error, ModelGatewayError) else "internal_error")
                terminal = True
            raise
        finally:
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()
