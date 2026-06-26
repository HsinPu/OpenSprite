"""
opensprite/llms/openai.py - OpenAI LLM 實作

實作 LLMProvider 介面，使用 OpenAI API（或相容 API 如 OpenRouter、vLLM）

"""
from dataclasses import replace
from typing import Any, Awaitable, Callable

from ..base import DefaultModelProviderMixin, LLMProvider, LLMResponse, ChatMessage
from ..reasoning import normalize_reasoning_effort, reasoning_config_or_default, reasoning_effort_from_config
from ..request_builder import OPENAI_CHAT_REQUEST_PROFILE, build_llm_request, normalize_openai_compatible_messages
from ..request_log_fields import log_llm_request_params
from ..request_modes import resolve_response_format
from ..openai_compatible import build_openai_client_kwargs
from ..openai_compatible import OpenAICompatibleClientMixin
from ..openai_compatible import build_openai_compatible_response
from .streaming import collect_openai_compatible_stream


_REQUEST_PROFILE = OPENAI_CHAT_REQUEST_PROFILE


def _openai_chat_model_supports_reasoning_effort(model: str) -> bool:
    """Return whether the OpenAI Chat Completions model likely accepts reasoning_effort."""
    name = str(model or "").strip().lower()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return name.startswith(("gpt-5", "o1", "o3", "o4"))


def _openai_chat_reasoning_params(
    model: str,
    reasoning_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build Chat Completions reasoning params, omitting them for non-reasoning models."""
    if not _openai_chat_model_supports_reasoning_effort(model):
        return {}
    effort = reasoning_effort_from_config(reasoning_config)
    return {"reasoning_effort": effort} if effort else {}


class OpenAILLM(OpenAICompatibleClientMixin, DefaultModelProviderMixin, LLMProvider):
    """
    OpenAI LLM 實作
    
    使用 OpenAI API（或相容 API 如 OpenRouter、本地 vLLM）
    """
    
    def __init__(
        self, 
        api_key: str, 
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
        default_headers: dict[str, str] | None = None,
        reasoning_effort: str = "",
    ):
        """
        初始化 OpenAI LLM
        
        參數：
            api_key: OpenAI API Key
            base_url: API 端點（可選，例如用 OpenRouter 或本地模型）
            default_model: 預設模型名稱
        """
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.default_headers = dict(default_headers or {})
        self.reasoning_effort = normalize_reasoning_effort(reasoning_effort)
        self.reasoning_config = reasoning_config_or_default(self.reasoning_effort)
        self._client_kwargs = build_openai_client_kwargs(
            api_key,
            base_url=base_url,
            default_headers=self.default_headers,
        )
        self.client = self._build_client()

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
        request_mode: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """
        呼叫 OpenAI Chat Completions API
        """
        _ = status_callback
        # 轉換成 OpenAI 格式
        api_messages = normalize_openai_compatible_messages(
            messages,
            include_reasoning_details=_REQUEST_PROFILE.include_reasoning_details,
        )
        
        # API 參數（None = 不帶該欄位，交給服務端預設）
        resolved_model = model or self.default_model
        request_profile = (
            replace(_REQUEST_PROFILE, max_tokens_param="max_completion_tokens")
            if _openai_chat_model_supports_reasoning_effort(resolved_model)
            else _REQUEST_PROFILE
        )
        params = build_llm_request(
            request_profile.options(
                model=resolved_model,
                messages=api_messages,
                tools=tools,
                max_tokens=max_tokens,
                extra_params=_openai_chat_reasoning_params(
                    resolved_model,
                    getattr(self, "reasoning_config", None),
                ),
                response_format=resolve_response_format(response_format, request_mode),
                stream=response_delta_callback is not None,
            )
        )
        log_llm_request_params("OpenAI", params, request_mode=request_mode)

        if response_delta_callback is not None:
            stream = await self.client.chat.completions.create(**params)
            return await collect_openai_compatible_stream(
                stream,
                provider_name="OpenAI",
                default_model=model or self.default_model,
                response_delta_callback=response_delta_callback,
                tool_input_delta_callback=tool_input_delta_callback,
                reasoning_delta_callback=reasoning_delta_callback,
            )

        # 呼叫 API
        response = await self.client.chat.completions.create(**params)
        return build_openai_compatible_response(
            response,
            provider_name="OpenAI",
            default_model=model or self.default_model,
        )
