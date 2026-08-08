"""Token counting helpers."""

from __future__ import annotations

import json
import math
import re
from typing import Any

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_WORD_OR_SYMBOL_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _load_tiktoken() -> Any | None:
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None
    return tiktoken


def _get_encoding(*, model: str | None = None, encoding_name: str | None = None) -> Any | None:
    tiktoken = _load_tiktoken()
    if tiktoken is None:
        return None

    if encoding_name:
        return tiktoken.get_encoding(encoding_name)

    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            pass

    return tiktoken.get_encoding("o200k_base")


def estimate_text_tokens(text: str) -> int:
    """Estimate token count when no model tokenizer is available."""
    if not text:
        return 0

    cjk_count = len(_CJK_RE.findall(text))
    non_cjk_text = _CJK_RE.sub(" ", text)

    estimated = cjk_count
    for token in _WORD_OR_SYMBOL_RE.findall(non_cjk_text):
        if token.isspace():
            continue
        if token.isalnum() or "_" in token:
            estimated += max(1, math.ceil(len(token) / 4))
        else:
            estimated += 1

    return estimated


def count_text_tokens(text: str, *, model: str | None = None, encoding_name: str | None = None) -> int:
    """Count tokens for text using tiktoken when available, else estimate."""
    value = text or ""
    encoding = _get_encoding(model=model, encoding_name=encoding_name)
    if encoding is None:
        return estimate_text_tokens(value)
    return len(encoding.encode(value))


def _message_to_text(message: Any) -> str:
    if isinstance(message, str):
        return message

    if isinstance(message, dict):
        payload = dict(message)
    else:
        payload = {
            "role": getattr(message, "role", None),
            "content": getattr(message, "content", None),
            "tool_call_id": getattr(message, "tool_call_id", None),
            "tool_calls": getattr(message, "tool_calls", None),
        }

    content = payload.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
        payload["content"] = "\n".join(parts)

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def count_messages_tokens(
    messages: list[Any], *, model: str | None = None, encoding_name: str | None = None
) -> int:
    """Count tokens across serialized chat messages."""
    return sum(
        count_text_tokens(_message_to_text(message), model=model, encoding_name=encoding_name)
        for message in messages
    )
