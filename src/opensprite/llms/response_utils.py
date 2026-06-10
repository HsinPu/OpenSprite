"""Common response helpers for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import LLMResponse, ToolCall
from .tool_args import parse_tool_arguments
from ..utils.log import logger


def safe_len(value: Any) -> str:
    try:
        return str(len(value))
    except Exception:
        return "n/a"


def coerce_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return json_safe(model_dump())
    return str(value)


def coerce_reasoning_details(value: Any) -> list[dict[str, Any]] | None:
    safe = json_safe(value)
    if not isinstance(safe, list):
        return None
    details = [item for item in safe if isinstance(item, dict)]
    return details or None


@dataclass(frozen=True)
class OpenAICompatibleMessageResult:
    message: Any | None
    choice: Any | None = None
    fallback_response: LLMResponse | None = None


def extract_openai_compatible_message(
    response: Any,
    *,
    provider_name: str,
    default_model: str,
    include_usage_in_fallback: bool = True,
) -> OpenAICompatibleMessageResult:
    """Extract the first response message or return the provider's empty fallback response."""
    choices = getattr(response, "choices", None)
    logger.info(
        "{} response summary: model={}, choices_type={}, choices_len={}",
        provider_name,
        getattr(response, "model", None),
        type(choices).__name__,
        safe_len(choices),
    )

    if not choices:
        logger.warning(
            "{} returned empty choices: response_id={}, model={}, object={}, usage={}",
            provider_name,
            getattr(response, "id", None),
            getattr(response, "model", None),
            getattr(response, "object", None),
            getattr(response, "usage", None),
        )
        return OpenAICompatibleMessageResult(
            message=None,
            fallback_response=LLMResponse(
                content="",
                model=getattr(response, "model", default_model),
                tool_calls=[],
                usage=usage_payload(getattr(response, "usage", None)) if include_usage_in_fallback else {},
            ),
        )

    choice: Any | None = None
    try:
        choice = choices[0]
        message = choice.message
    except Exception:
        logger.exception(
            "{} response parse failed: response_type={}, model={}, choices_type={}, choices_len={}, choices_preview={}",
            provider_name,
            type(response).__name__,
            getattr(response, "model", None),
            type(choices).__name__,
            safe_len(choices),
            repr(choices)[:500],
        )
        return OpenAICompatibleMessageResult(
            message=None,
            choice=choice,
            fallback_response=LLMResponse(
                content="",
                model=getattr(response, "model", default_model),
                tool_calls=[],
                usage=usage_payload(getattr(response, "usage", None)) if include_usage_in_fallback else {},
            ),
        )

    if message is None:
        logger.warning("{} response missing message payload; returning empty response", provider_name)
        return OpenAICompatibleMessageResult(
            message=None,
            choice=choice,
            fallback_response=LLMResponse(
                content="",
                model=getattr(response, "model", default_model),
                tool_calls=[],
                usage=usage_payload(getattr(response, "usage", None)) if include_usage_in_fallback else {},
            ),
        )

    return OpenAICompatibleMessageResult(message=message, choice=choice)


def _get_attr_or_item(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def extract_openai_compatible_tool_calls(message: Any, *, provider_name: str) -> list[ToolCall]:
    """Extract tool calls from an OpenAI-compatible response message."""
    tool_calls: list[ToolCall] = []
    raw_tool_calls = _get_attr_or_item(message, "tool_calls")
    if not raw_tool_calls:
        return tool_calls

    for raw_tool_call in raw_tool_calls:
        function = _get_attr_or_item(raw_tool_call, "function")
        if function is None:
            logger.warning("{} tool call missing function payload; skipping", provider_name)
            continue

        tool_name = _get_attr_or_item(function, "name", "") or ""
        args = parse_tool_arguments(
            _get_attr_or_item(function, "arguments"),
            provider_name=provider_name,
            tool_name=tool_name,
        )

        tool_calls.append(
            ToolCall(
                id=_get_attr_or_item(raw_tool_call, "id", "") or f"tool_call_{len(tool_calls) + 1}",
                name=tool_name,
                arguments=args,
            )
        )

    return tool_calls


def usage_payload(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        try:
            return dict(usage.model_dump(exclude_none=True))
        except Exception:
            pass
    if isinstance(usage, dict):
        return dict(usage)
    return {
        key: getattr(usage, key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if getattr(usage, key, None) is not None
    }
