"""
opensprite/llms/minimax.py - MiniMax LLM 實作

實作 LLMProvider 介面，使用 MiniMax API
官網：https://www.minimax.io/
"""
import asyncio
import random
from typing import Any, Awaitable, Callable

from .base import LLMProvider, LLMResponse, ChatMessage
from .retry import looks_like_transient_transport_error
from .request_builder import OPENAI_REASONING_HISTORY_REQUEST_PROFILE, build_llm_request, normalize_openai_compatible_messages
from .response_utils import coerce_content as _coerce_content
from .response_utils import coerce_reasoning_details as _coerce_reasoning_details
from .response_utils import extract_openai_compatible_message
from .response_utils import extract_openai_compatible_tool_calls
from .response_utils import safe_len as _safe_len
from ..utils.log_redaction import redact_log_preview
from ..utils.log import logger


_REQUEST_PROFILE = OPENAI_REASONING_HISTORY_REQUEST_PROFILE


def _preview_text(value: Any, max_chars: int = 240) -> str:
    text = redact_log_preview(_coerce_content(value)).replace("\n", "\\n")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _contains_system_reminder(value: Any) -> bool:
    return "<system-reminder>" in _coerce_content(value)


def _count_system_reminders(value: Any) -> int:
    return _coerce_content(value).count("<system-reminder>")


def _is_minimax_overloaded_error(exc: BaseException) -> bool:
    """MiniMax 在流量過載時回傳 HTTP 529（OpenAI SDK 為 InternalServerError）。"""
    code = getattr(exc, "status_code", None)
    if code == 529:
        return True
    if looks_like_transient_transport_error(exc):
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("type") == "overloaded_error":
            return True
    return False


class MiniMaxLLM(LLMProvider):
    """
    MiniMax LLM 實作
    
    使用 MiniMax API（OpenAI 相容）
    API 文件：https://www.minimax.io/docs/api
    """
    
    def __init__(
        self, 
        api_key: str, 
        default_model: str = "MiniMax-M2.5",
        base_url: str | None = None,
    ):
        """
        初始化 MiniMax LLM
        
        參數：
            api_key: MiniMax API Key
            default_model: 預設模型名稱
        """
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = (base_url or "https://api.minimax.io/v1").rstrip("/")
        self._client_kwargs = {
            "api_key": api_key,
            "base_url": self.base_url,
        }
        self.client = self._build_client()

    def _build_client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(**self._client_kwargs)

    async def _chat_completions_create(
        self,
        params: dict[str, Any],
        *,
        status_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> Any:
        """呼叫 chat completions；遇 MiniMax 529（overloaded_error）時採指數退避重試。"""
        from openai import InternalServerError

        max_attempts = 5
        base_delay_sec = 2.0

        for attempt in range(max_attempts):
            try:
                return await self.client.chat.completions.create(**params)
            except InternalServerError as e:
                if not _is_minimax_overloaded_error(e):
                    raise
                if attempt >= max_attempts - 1:
                    logger.error(
                        "MiniMax API 流量過載（529）已重試 {} 次仍失敗；可稍後再試、升級方案或使用高速模型："
                        "https://platform.minimax.io/subscribe/token-plan | {}",
                        max_attempts,
                        e,
                    )
                    raise
                delay = base_delay_sec * (2**attempt) + random.uniform(0, 1.0)
                logger.warning(
                    "MiniMax API 流量過載（529），{:.1f} 秒後重試（第 {}／{} 次）",
                    delay,
                    attempt + 1,
                    max_attempts,
                )
                if status_callback is not None:
                    notice = (
                        "MiniMax 目前流量較高（HTTP 529），"
                        f"約 {delay:.0f} 秒後會自動重試（第 {attempt + 1}／{max_attempts} 次）。"
                        "若經常發生，可考慮升級方案或使用高速模型："
                        "https://platform.minimax.io/subscribe/token-plan"
                    )
                    try:
                        await status_callback(notice)
                    except Exception as cb_err:
                        logger.warning("MiniMax status_callback 失敗（仍會繼續重試）：{}", cb_err)
                await asyncio.sleep(delay)
    
    async def chat(
        self, 
        messages: list[ChatMessage], 
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        status_callback: Callable[[str], Awaitable[None]] | None = None,
        response_delta_callback: Callable[[str], Awaitable[None]] | None = None,
        tool_input_delta_callback: Callable[[str, str, str, int], Awaitable[None]] | None = None,
        reasoning_delta_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """
        呼叫 MiniMax Chat Completions API
        """
        _ = response_delta_callback
        _ = tool_input_delta_callback
        _ = reasoning_delta_callback
        # 轉換成 OpenAI 格式
        api_messages = normalize_openai_compatible_messages(
            messages,
            include_reasoning_details=_REQUEST_PROFILE.include_reasoning_details,
        )

        request_reminder_hits: list[str] = []
        for index, msg in enumerate(api_messages, start=1):
            content = msg.get("content", "")
            text = content if isinstance(content, str) else _coerce_content(content)
            if not _contains_system_reminder(text):
                continue
            request_reminder_hits.append(f"{index}:{msg.get('role', '?')}")
            logger.warning(
                "MiniMax request contains system-reminder: index={} role={} len={} preview={}",
                index,
                msg.get("role", "?"),
                len(text),
                _preview_text(text),
            )
        request_reminder_count = sum(_count_system_reminders(msg.get("content", "")) for msg in api_messages)
        if request_reminder_hits:
            logger.warning(
                "MiniMax request system-reminder summary: message_count={} reminder_count={} hits={}",
                len(api_messages),
                request_reminder_count,
                ", ".join(request_reminder_hits),
            )

        params = build_llm_request(
            _REQUEST_PROFILE.options(
                model=model or self.default_model,
                messages=api_messages,
                tools=tools,
                max_tokens=max_tokens,
            )
        )

        # 呼叫 API（含 529 過載重試；可選通知使用者後再退避）
        response = await self._chat_completions_create(params, status_callback=status_callback)
        message_result = extract_openai_compatible_message(
            response,
            provider_name="MiniMax",
            default_model=model or self.default_model,
            include_usage_in_fallback=False,
        )
        # Debug: log raw MiniMax response for diagnostics
        logger.debug(
            "MiniMax raw response: id={}, model={}, usage={}, finish_reason={}",
            getattr(response, "id", None),
            getattr(response, "model", None),
            getattr(response, "usage", None),
            getattr(getattr(message_result.choice, "finish_reason", None), "value", None),
        )

        if message_result.fallback_response is not None:
            return message_result.fallback_response
        message = message_result.message

        # Log raw message content for debugging hidden blocks
        raw_message_content = getattr(message, "content", "")
        reasoning_details = _coerce_reasoning_details(getattr(message, "reasoning_details", None))
        logger.info(
            "MiniMax raw message content: len={} reasoning_details={} preview={}",
            len(raw_message_content) if raw_message_content else 0,
            len(reasoning_details or []),
            _preview_text(raw_message_content, max_chars=200),
        )
        if _contains_system_reminder(raw_message_content):
            response_reminder_count = _count_system_reminders(raw_message_content)
            logger.warning(
                "MiniMax response contains system-reminder: len={} reminder_count={} tool_calls_count={} preview={}",
                len(raw_message_content),
                response_reminder_count,
                _safe_len(getattr(message, "tool_calls", None)),
                _preview_text(raw_message_content),
            )
            logger.warning(
                "MiniMax system-reminder provenance: request_reminder_count={} response_reminder_count={} source={}",
                request_reminder_count,
                response_reminder_count,
                "model_generated" if request_reminder_count == 0 else "request_echo_or_model_continuation",
            )

        # Log raw tool calls for debugging
        raw_tool_calls = getattr(message, "tool_calls", None)
        if raw_tool_calls:
            for tc in raw_tool_calls:
                func = getattr(tc, "function", None)
                raw_arguments = getattr(func, "arguments", None)
                logger.info(
                    "MiniMax raw tool_call: id={}, name={}, arguments_type={}, arguments_preview={}",
                    getattr(tc, "id", None),
                    getattr(func, "name", None),
                    type(raw_arguments).__name__,
                    _preview_text(raw_arguments, max_chars=200) if raw_arguments is not None else "None",
                )
                if _contains_system_reminder(raw_arguments):
                    logger.warning(
                        "MiniMax tool_call arguments contain system-reminder: id={} name={} preview={}",
                        getattr(tc, "id", None),
                        getattr(func, "name", None),
                        _preview_text(raw_arguments),
                    )

        tool_calls = extract_openai_compatible_tool_calls(message, provider_name="MiniMax")
        
        return LLMResponse(
            content=_coerce_content(getattr(message, "content", "")),
            model=getattr(response, "model", model or self.default_model),
            tool_calls=tool_calls,
            reasoning_details=reasoning_details,
        )
    
    def get_default_model(self) -> str:
        return self.default_model

    def recover_after_error(self, error: BaseException) -> bool:
        _ = error
        try:
            self.client = self._build_client()
            return True
        except Exception:
            return False
