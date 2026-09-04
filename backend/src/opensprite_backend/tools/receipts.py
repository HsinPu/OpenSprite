"""Hash-chained HMAC receipts for approved consequential Tool calls."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import secrets
from threading import Lock
from typing import Protocol
from uuid import uuid4

from ..app_paths import AppPaths
from ..atomic_file import atomic_write
from .approval import ToolApprovalGrant
from .definition import ToolContext, ToolDefinition


class ToolReceiptError(Exception):
    pass


class ToolReceiptWriter(Protocol):
    async def record_authorized(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        grant: ToolApprovalGrant,
    ) -> None: ...

    async def record_result(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        grant: ToolApprovalGrant,
        *,
        status: str,
        result: str,
    ) -> None: ...


class FileToolReceiptWriter:
    def __init__(
        self,
        paths: AppPaths,
        *,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._directory = paths.tool_receipts_dir
        self._key_file = paths.tool_receipt_key_file
        self._clock = clock
        self._lock = Lock()
        self._previous_hash: str | None = None

    async def record_authorized(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        grant: ToolApprovalGrant,
    ) -> None:
        await asyncio.to_thread(
            self._record,
            definition,
            context,
            grant,
            "authorized",
            None,
        )

    async def record_result(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        grant: ToolApprovalGrant,
        *,
        status: str,
        result: str,
    ) -> None:
        if status not in {"completed", "failed"}:
            raise ToolReceiptError
        await asyncio.to_thread(
            self._record,
            definition,
            context,
            grant,
            status,
            sha256(result.encode("utf-8")).hexdigest(),
        )

    def _record(
        self,
        definition: ToolDefinition,
        context: ToolContext,
        grant: ToolApprovalGrant,
        status: str,
        result_hash: str | None,
    ) -> None:
        if definition.source_id is None:
            raise ToolReceiptError
        with self._lock:
            try:
                key = self._load_or_create_key()
                previous_hash = self._previous_hash or self._read_previous_hash()
                now = self._clock()
                body = {
                    "version": 2,
                    "receiptId": str(uuid4()),
                    "approvalId": grant.approval_id,
                    "actor": "local_user",
                    "runId": context.run_id,
                    "conversationId": context.conversation_id,
                    "workspaceId": context.workspace.id,
                    "workspaceRevision": context.workspace.revision,
                    "workspaceRootHash": context.workspace.root_hash,
                    "serverId": definition.source_id,
                    "toolId": definition.name,
                    "requestHash": grant.request_hash,
                    "status": status,
                    "resultHash": result_hash,
                    "recordedAt": now.isoformat().replace("+00:00", "Z"),
                    "previousReceiptHash": previous_hash,
                }
                signature = hmac.new(key, _canonical(body), "sha256").hexdigest()
                record = {**body, "signature": signature}
                encoded = _canonical(record) + b"\n"
                self._directory.mkdir(parents=True, exist_ok=True)
                path = self._directory / f"{now.date().isoformat()}.jsonl"
                descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
                try:
                    os.write(descriptor, encoded)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                self._previous_hash = sha256(encoded.rstrip(b"\n")).hexdigest()
            except ToolReceiptError:
                raise
            except Exception as error:
                raise ToolReceiptError from error

    def _load_or_create_key(self) -> bytes:
        try:
            key = self._key_file.read_bytes()
        except FileNotFoundError:
            key = secrets.token_bytes(32)
            atomic_write(self._key_file, key)
        if len(key) != 32:
            raise ToolReceiptError
        return key

    def _read_previous_hash(self) -> str | None:
        if not self._directory.exists():
            return None
        files = sorted(self._directory.glob("*.jsonl"))
        if not files:
            return None
        data = files[-1].read_bytes()
        if len(data) > 16 * 1024 * 1024:
            raise ToolReceiptError
        lines = [line for line in data.splitlines() if line]
        return None if not lines else sha256(lines[-1]).hexdigest()


def verify_tool_receipts(paths: AppPaths) -> bool:
    try:
        key = paths.tool_receipt_key_file.read_bytes()
        if len(key) != 32:
            return False
        previous: str | None = None
        for path in sorted(paths.tool_receipts_dir.glob("*.jsonl")):
            data = path.read_bytes()
            if len(data) > 16 * 1024 * 1024:
                return False
            for line in data.splitlines():
                raw = json.loads(line)
                if not isinstance(raw, dict) or raw.get("previousReceiptHash") != previous:
                    return False
                signature = raw.pop("signature", None)
                if not isinstance(signature, str) or not hmac.compare_digest(
                    signature,
                    hmac.new(key, _canonical(raw), "sha256").hexdigest(),
                ):
                    return False
                previous = sha256(line).hexdigest()
        return True
    except Exception:
        return False


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
