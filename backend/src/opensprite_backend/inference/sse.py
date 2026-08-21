"""Bounded strict parser for upstream server-sent event data fields."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


MAX_STREAM_BYTES = 16 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024


class StreamFormatError(Exception):
    pass


async def iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
    content_type = response.headers.get("content-type", "")
    if content_type.split(";", 1)[0].strip().lower() != "text/event-stream":
        raise StreamFormatError

    total = 0
    buffer = bytearray()
    data_lines: list[bytes] = []
    event_size = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > MAX_STREAM_BYTES:
            raise StreamFormatError
        buffer.extend(chunk)
        while True:
            newline = buffer.find(b"\n")
            if newline < 0:
                break
            line = bytes(buffer[:newline])
            del buffer[: newline + 1]
            if line.endswith(b"\r"):
                line = line[:-1]
            if not line:
                if data_lines:
                    raw = b"\n".join(data_lines)
                    try:
                        yield raw.decode("utf-8")
                    except UnicodeDecodeError as error:
                        raise StreamFormatError from error
                data_lines = []
                event_size = 0
                continue
            if line.startswith(b":"):
                continue
            field, separator, value = line.partition(b":")
            if not separator:
                raise StreamFormatError
            if value.startswith(b" "):
                value = value[1:]
            if field == b"data":
                event_size += len(value)
                if event_size > MAX_EVENT_BYTES:
                    raise StreamFormatError
                data_lines.append(value)
            elif field not in {b"event", b"id", b"retry"}:
                raise StreamFormatError
        if len(buffer) > MAX_EVENT_BYTES:
            raise StreamFormatError
    if buffer or data_lines:
        raise StreamFormatError


def load_json_object(data: str) -> dict[str, object]:
    try:
        value = json.loads(data, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        raise StreamFormatError from error
    if type(value) is not dict:
        raise StreamFormatError
    return value


def load_json_arguments(data: str) -> dict[str, object]:
    if len(data.encode("utf-8")) > 65536:
        raise StreamFormatError
    return load_json_object(data)


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
