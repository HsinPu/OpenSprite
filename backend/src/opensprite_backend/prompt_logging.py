"""Opt-in full model-request receipts for local debugging."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from typing import Protocol
from uuid import UUID

from .app_paths import AppPaths
from .inference.models import ModelMessage, ModelToolDefinition

_MAX_PROMPT_LOG_BYTES = 8 * 1024 * 1024


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
        max_output_tokens: int,
        messages: tuple[ModelMessage, ...],
        tools: tuple[ModelToolDefinition, ...],
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
        max_output_tokens: int,
        messages: tuple[ModelMessage, ...],
        tools: tuple[ModelToolDefinition, ...],
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
            max_output_tokens=max_output_tokens,
            messages=messages,
            tools=tools,
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
        max_output_tokens: int,
        messages: tuple[ModelMessage, ...],
        tools: tuple[ModelToolDefinition, ...],
    ) -> bytes:
        parts = [
            "# OpenSprite Full Model Request Log",
            "",
            f"- Request sequence: {request_sequence}",
            f"- Request kind: {request_kind}",
            f"- Run ID: {run_id}",
            f"- Created at: {created_at.isoformat(timespec='milliseconds')}",
            f"- Provider ID: {provider_id}",
            f"- Model ID: {model_id}",
            f"- Response mode: {response_mode}",
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
            if message.tool_calls:
                parts.extend(["Tool calls:", ""])
                for call in message.tool_calls:
                    parts.extend([f"- {call.name} ({call.call_id}): {call.arguments}"])
                parts.append("")
            if message.tool_call_id is not None:
                parts.extend([f"Tool call ID: {message.tool_call_id}", f"Tool name: {message.tool_name}", ""])
        parts.extend(["## Tool definitions", ""])
        if not tools:
            parts.append("(none)")
        else:
            for tool in tools:
                parts.extend([f"- {tool.name}: {tool.description}", ""])
        return "\n".join(parts).encode("utf-8")
