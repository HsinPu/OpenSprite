"""Common request builders for LLM provider transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import ChatMessage


@dataclass(frozen=True)
class LLMRequestOptions:
    """Provider-neutral inputs for LLM request payloads with optional fields."""

    model: str
    messages: list[dict[str, Any]]
    input_key: str = "messages"
    tools: list[dict[str, Any]] | None = None
    max_tokens: int | None = None
    max_tokens_param: str = "max_tokens"
    stream: bool = False
    tool_choice: Any = "auto"
    extra_body: dict[str, Any] | None = None
    request_overrides: dict[str, Any] | None = None


def build_llm_request(options: LLMRequestOptions) -> dict[str, Any]:
    """Build an LLM request payload while omitting unset optional fields."""
    params: dict[str, Any] = {
        "model": options.model,
        options.input_key: options.messages,
    }

    if options.max_tokens is not None:
        params[options.max_tokens_param] = options.max_tokens

    if options.tools:
        params["tools"] = options.tools
        if options.tool_choice is not None:
            params["tool_choice"] = options.tool_choice

    if options.stream:
        params["stream"] = True

    if options.extra_body:
        params["extra_body"] = dict(options.extra_body)

    if options.request_overrides:
        overrides = dict(options.request_overrides)
        extra_body = overrides.pop("extra_body", None)
        if isinstance(extra_body, dict):
            params["extra_body"] = {**dict(params.get("extra_body") or {}), **extra_body}
        params.update(overrides)

    return params


def normalize_openai_compatible_messages(
    messages: list[ChatMessage | dict[str, Any]],
    *,
    include_reasoning_details: bool = False,
) -> list[dict[str, Any]]:
    """Convert internal chat messages into OpenAI-compatible message payloads."""
    api_messages: list[dict[str, Any]] = []

    for message in messages:
        if isinstance(message, dict):
            msg = {
                "role": message.get("role", "?"),
                "content": message.get("content", ""),
            }
            if message.get("tool_call_id"):
                msg["tool_call_id"] = message["tool_call_id"]
            if message.get("tool_calls"):
                msg["tool_calls"] = message["tool_calls"]
            if include_reasoning_details and message.get("reasoning_details"):
                msg["reasoning_details"] = message["reasoning_details"]
        else:
            msg = {"role": message.role, "content": message.content}
            if message.tool_call_id:
                msg["tool_call_id"] = message.tool_call_id
            if message.tool_calls:
                msg["tool_calls"] = message.tool_calls
            if include_reasoning_details and message.reasoning_details:
                msg["reasoning_details"] = message.reasoning_details
        api_messages.append(msg)

    return api_messages
