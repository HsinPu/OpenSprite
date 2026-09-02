"""Short-lived, single-use human approval for consequential Tool calls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from typing import Protocol
from uuid import uuid4

from ..conversations.models import RunEventType
from ..conversations.repository import ConversationRepository, ConversationStoreError
from ..models import (
    ToolApprovalDecision,
    ToolApprovalDecisionResponse,
    ToolApprovalDetail,
    ToolApprovalErrorCode,
)
from .definition import ToolContext, ToolDefinition, ToolSource


_APPROVAL_TTL_SECONDS = 600
_MAX_ARGUMENT_BYTES = 65_536


class ToolApprovalError(Exception):
    def __init__(self, code: ToolApprovalErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class ToolApprovalDenied(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ToolApprovalGrant:
    approval_id: str
    request_hash: str


class ToolApprovalAuthorizer(Protocol):
    async def authorize(
        self,
        definition: ToolDefinition,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolApprovalGrant: ...


class ToolApprovalOperations(Protocol):
    async def get(self, approval_id: str) -> ToolApprovalDetail: ...

    async def decide(
        self,
        approval_id: str,
        decision: ToolApprovalDecision,
    ) -> ToolApprovalDecisionResponse: ...


@dataclass(slots=True)
class _PendingApproval:
    detail: ToolApprovalDetail
    future: asyncio.Future[ToolApprovalDecision]
    decided: bool = False


class ToolApprovalManager:
    def __init__(
        self,
        repository: ConversationRepository,
        *,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._lock = asyncio.Lock()
        self._pending: dict[str, _PendingApproval] = {}

    async def authorize(
        self,
        definition: ToolDefinition,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolApprovalGrant:
        if definition.source is not ToolSource.MCP or definition.source_id is None:
            raise ToolApprovalDenied
        encoded = _canonical_arguments(arguments)
        now = self._clock()
        approval_id = str(uuid4())
        detail = ToolApprovalDetail(
            id=approval_id,
            runId=context.run_id,
            conversationId=context.conversation_id,
            toolId=definition.name,
            toolName=definition.display_name or definition.name,
            serverId=definition.source_id,
            arguments=dict(arguments),
            argumentHash=sha256(encoded).hexdigest(),
            createdAt=now,
            expiresAt=now + timedelta(seconds=_APPROVAL_TTL_SECONDS),
        )
        pending = _PendingApproval(
            detail=detail,
            future=asyncio.get_running_loop().create_future(),
        )
        async with self._lock:
            self._pending[approval_id] = pending
        try:
            await asyncio.to_thread(
                self._repository.append_run_event,
                context.run_id,
                RunEventType.TOOL_APPROVAL_REQUESTED,
                {
                    "approvalId": approval_id,
                    "toolName": definition.name,
                    "toolDisplayName": detail.toolName,
                    "serverId": definition.source_id,
                    "argumentHash": detail.argumentHash,
                    "expiresAt": detail.expiresAt.isoformat().replace("+00:00", "Z"),
                },
            )
            try:
                async with asyncio.timeout(_APPROVAL_TTL_SECONDS):
                    decision = await pending.future
            except TimeoutError as error:
                await self._record_decision(context.run_id, approval_id, "expired")
                raise ToolApprovalDenied from error
            if decision is ToolApprovalDecision.DENY:
                await self._record_decision(context.run_id, approval_id, "deny")
                raise ToolApprovalDenied
            await self._record_decision(context.run_id, approval_id, "allow_once")
            return ToolApprovalGrant(
                approval_id=approval_id,
                request_hash=detail.argumentHash,
            )
        finally:
            async with self._lock:
                self._pending.pop(approval_id, None)

    async def get(self, approval_id: str) -> ToolApprovalDetail:
        async with self._lock:
            pending = self._pending.get(approval_id)
            if pending is None:
                raise ToolApprovalError(ToolApprovalErrorCode.NOT_FOUND)
            if self._clock() >= pending.detail.expiresAt:
                raise ToolApprovalError(ToolApprovalErrorCode.APPROVAL_EXPIRED)
            return pending.detail

    async def decide(
        self,
        approval_id: str,
        decision: ToolApprovalDecision,
    ) -> ToolApprovalDecisionResponse:
        async with self._lock:
            pending = self._pending.get(approval_id)
            if pending is None:
                raise ToolApprovalError(ToolApprovalErrorCode.NOT_FOUND)
            if self._clock() >= pending.detail.expiresAt:
                raise ToolApprovalError(ToolApprovalErrorCode.APPROVAL_EXPIRED)
            if pending.decided or pending.future.done():
                raise ToolApprovalError(ToolApprovalErrorCode.APPROVAL_ALREADY_DECIDED)
            pending.decided = True
            pending.future.set_result(decision)
        return ToolApprovalDecisionResponse(id=approval_id, decision=decision)

    async def _record_decision(
        self,
        run_id: str,
        approval_id: str,
        decision: str,
    ) -> None:
        try:
            await asyncio.to_thread(
                self._repository.append_run_event,
                run_id,
                RunEventType.TOOL_APPROVAL_DECIDED,
                {"approvalId": approval_id, "decision": decision},
            )
        except ConversationStoreError as error:
            raise ToolApprovalError(ToolApprovalErrorCode.DATABASE_UNAVAILABLE) from error


class UnavailableToolApprovals:
    async def get(self, approval_id: str) -> ToolApprovalDetail:
        del approval_id
        raise ToolApprovalError(ToolApprovalErrorCode.NOT_FOUND)

    async def decide(
        self,
        approval_id: str,
        decision: ToolApprovalDecision,
    ) -> ToolApprovalDecisionResponse:
        del approval_id, decision
        raise ToolApprovalError(ToolApprovalErrorCode.NOT_FOUND)


def _canonical_arguments(arguments: dict[str, object]) -> bytes:
    try:
        encoded = json.dumps(
            arguments,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ToolApprovalDenied from error
    if len(encoded) > _MAX_ARGUMENT_BYTES:
        raise ToolApprovalDenied
    return encoded
