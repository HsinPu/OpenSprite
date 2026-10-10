"""Opt-in full model-request receipts for local debugging."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from dataclasses import asdict
from functools import partial
import hashlib
import json
import os
import logging
from pathlib import Path
from queue import Empty, Queue
import tempfile
from threading import Condition, Thread
from time import monotonic
from typing import Protocol
from uuid import UUID

from .app_paths import AppPaths
from .inference.models import ModelMessage
from .inference.models import ModelRequest
from .system_prompt import FileSystemPromptLogWriter, RenderedSystemPrompt

_MAX_PROMPT_LOG_BYTES = 8 * 1024 * 1024
_LOGGER = logging.getLogger("opensprite.prompt_recording")


class PromptLogWriter(Protocol):
    def write(
        self,
        *,
        run_id: str,
        created_at: datetime,
        request_kind: str,
        request_sequence: int,
        provider_id: str,
        model_id: str,
        response_mode: str,
        reasoning_effort: str | None = None,
        max_output_tokens: int,
        messages: tuple[ModelMessage, ...],

    ) -> None: ...


class PromptLogError(Exception):
    """Sanitized failure while writing a full prompt receipt."""


class FilePromptLogWriter:
    """Write one immutable complete request receipt per model request."""

    def __init__(self, app_paths: AppPaths) -> None:
        self._home = app_paths.home
        self._root = app_paths.prompt_logs_dir

    def write(
        self,
        *,
        run_id: str,
        created_at: datetime,
        request_kind: str,
        request_sequence: int,
        provider_id: str,
        model_id: str,
        response_mode: str,
        reasoning_effort: str | None = None,
        max_output_tokens: int,
        messages: tuple[ModelMessage, ...],

    ) -> None:
        try:
            parsed_run_id = UUID(run_id)
        except (TypeError, ValueError, AttributeError) as error:
            raise PromptLogError from error
        if str(parsed_run_id) != run_id or not request_kind or not 1 <= request_sequence <= 10_000:
            raise PromptLogError
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise PromptLogError
        created_local = created_at.astimezone()
        payload = self._render(
            run_id=run_id,
            created_at=created_local,
            request_kind=request_kind,
            request_sequence=request_sequence,
            provider_id=provider_id,
            model_id=model_id,
            response_mode=response_mode,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            messages=messages,

        )
        if len(payload) > _MAX_PROMPT_LOG_BYTES:
            raise PromptLogError
        dated_root = self._root / created_local.date().isoformat() / run_id
        temporary_path: Path | None = None
        descriptor: int | None = None
        try:
            for directory in (self._home, self._root, dated_root.parent, dated_root):
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                if os.name != "nt":
                    directory.chmod(0o700)
            filename = f"{request_sequence:04d}-{request_kind}.md"
            target = dated_root / filename
            descriptor, temporary_name = tempfile.mkstemp(
                dir=dated_root,
                prefix=f".{filename}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = None
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, target)
            temporary_path = None
            if os.name != "nt":
                target.chmod(0o600)
        except Exception as error:
            raise PromptLogError from error
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _render(
        *,
        run_id: str,
        created_at: datetime,
        request_kind: str,
        request_sequence: int,
        provider_id: str,
        model_id: str,
        response_mode: str,
        reasoning_effort: str | None = None,
        max_output_tokens: int,
        messages: tuple[ModelMessage, ...],

    ) -> bytes:
        normalized = {
            "providerId": provider_id, "modelId": model_id,
            "responseMode": response_mode, "maxOutputTokens": max_output_tokens,
            "reasoningEffort": reasoning_effort,
            "messages": [asdict(message) for message in messages],

        }
        request_hash = hashlib.sha256(json.dumps(
            normalized, sort_keys=True, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        parts = [
            "# OpenSprite Full Model Request Log",
            "",
            f"- Request sequence: {request_sequence}",
            f"- Request kind: {request_kind}",
            f"- Run ID: {run_id}",
            f"- Normalized request SHA-256: {request_hash}",
            f"- Created at: {created_at.isoformat(timespec='milliseconds')}",
            f"- Provider ID: {provider_id}",
            f"- Model ID: {model_id}",
            f"- Response mode: {response_mode}",
            f"- Effective reasoning effort: {reasoning_effort or '(default)'}",
            f"- Max output tokens: {max_output_tokens}",
            "",
            "## Messages sent to the model",
            "",
        ]
        for index, message in enumerate(messages, start=1):
            parts.extend(
                [
                    f"### Message {index} — {message.role}",
                    "",
                    message.content,
                    "",
                ]
            )
        return "\n".join(parts).encode("utf-8")


class PromptRecorder:
    """A bounded, lazy product recorder; disk I/O never blocks an inference."""

    def __init__(self, system_writer: FileSystemPromptLogWriter, request_writer: PromptLogWriter,
                 *, capacity: int = 4) -> None:
        if type(capacity) is not int or not 1 <= capacity <= 16:
            raise ValueError("invalid recording capacity")
        self._system_writer = system_writer
        self._request_writer = request_writer
        self._capacity = capacity
        self._queue: Queue[tuple[str, Callable[[], None]]] = Queue(maxsize=capacity)
        self._condition = Condition()
        self._pending = 0
        self._closed = False
        self._worker: Thread | None = None

    def record_system(self, *, run_id: str, prompt: RenderedSystemPrompt) -> None:
        self._submit(run_id, len(prompt.content.encode("utf-8")), partial(
            self._system_writer.write, run_id=run_id, created_at=prompt.created_at,
            locale_source=prompt.locale_source, time_zone_source=prompt.time_zone_source,
            settings_fallback=prompt.settings_fallback, content=prompt.content))

    def record_request(self, *, run_id: str, request_sequence: int,
                       request: ModelRequest, created_at: datetime) -> None:
        size = sum(len(message.content.encode("utf-8")) for message in request.messages)
        self._submit(run_id, size, partial(
            self._request_writer.write, run_id=run_id, created_at=created_at,
            request_sequence=request_sequence, request_kind=f"step-{request_sequence:03d}",
            provider_id=request.provider_id, model_id=request.model_id,
            response_mode=request.response_mode,
            reasoning_effort=request.reasoning_resolution.effective if request.reasoning_resolution else None,
            max_output_tokens=request.max_output_tokens, messages=request.messages))

    def _submit(self, run_id: str, size: int, write: Callable[[], None]) -> None:
        with self._condition:
            if self._closed or size > _MAX_PROMPT_LOG_BYTES or self._pending >= self._capacity:
                _LOGGER.warning("prompt_recording_skipped run_id=%s", run_id)
                return
            self._queue.put_nowait((run_id, write))
            self._pending += 1
            if self._worker is None:
                self._worker = Thread(target=self._consume, name="opensprite-prompt-recorder", daemon=True)
                self._worker.start()

    def _consume(self) -> None:
        while True:
            try:
                run_id, write = self._queue.get(timeout=.1)
            except Empty:
                with self._condition:
                    if self._closed:
                        return
                continue
            try:
                write()
            except Exception:
                # Never include an exception, a Prompt, or a Provider response in diagnostics.
                _LOGGER.warning("prompt_recording_unavailable run_id=%s", run_id)
            finally:
                with self._condition:
                    self._pending -= 1
                    self._condition.notify_all()

    async def flush(self, *, timeout: float = 2) -> bool:
        drained = await asyncio.to_thread(self._drain, timeout)
        if not drained:
            _LOGGER.warning("prompt_recording_flush_timeout")
        return drained

    def _drain(self, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: self._pending == 0, timeout=timeout)

    async def aclose(self, *, timeout: float = 2) -> None:
        with self._condition:
            self._closed = True
        started = monotonic()
        await self.flush(timeout=timeout)
        if self._worker is not None:
            await asyncio.to_thread(self._worker.join, max(0, timeout - (monotonic() - started)))
