"""Runtime config reload helpers for AgentLoop."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from ...config import Config, ToolsConfig, WebSearchToolConfig
from ...core.ports.llm import LLMProvider
from ...core.ports.llm_runtime import LlmRuntimeFactory
from ...modules.media.router import MediaRouter, media_router_status
from ...modules.tools.registry import ToolRegistry
from opensprite.core.logging import logger
from ..llm.runtime_provider import is_llm_configured


MediaRouterReloader = Callable[[MediaRouter | None, Config], MediaRouter]
WebSearchToolReloader = Callable[
    [ToolRegistry, WebSearchToolConfig],
    dict[str, bool],
]


class BrowserToolReloader(Protocol):
    """Reload application-owned Browser tools in an existing registry."""

    def __call__(
        self,
        registry: ToolRegistry,
        *,
        get_session_id: Callable[[], str | None],
        tools_config: ToolsConfig | None = None,
    ) -> dict[str, bool]: ...


def refresh_consolidator_llm(consolidator: Any | None, provider: LLMProvider) -> None:
    """Point optional background document consolidators at the active LLM."""
    if consolidator is None:
        return
    if hasattr(consolidator, "provider"):
        consolidator.provider = provider
    if hasattr(consolidator, "model"):
        consolidator.model = provider.get_default_model()


def reload_agent_llm_from_config(
    agent: Any,
    config: Config,
    *,
    llm_runtime_factory: LlmRuntimeFactory,
) -> dict[str, Any]:
    """Reload the active chat LLM from an already persisted Config."""
    provider, llm_runtime = llm_runtime_factory.create_configured(
        config,
        fallback_app_home=agent.app_home,
    )

    agent.provider = provider
    agent.llm_output_reserve_tokens = config.agent.context_output_reserve_tokens
    agent.llm_context_window_tokens = llm_runtime.context_window_tokens
    agent.llm_configured = is_llm_configured(config)

    agent.prompt_budget.provider = provider
    agent.execution_engine.provider = provider
    agent.execution_engine.context_compaction_token_budget = agent._effective_context_token_budget()
    agent.execution_engine.context_window_tokens = agent.llm_context_window_tokens
    agent.execution_engine.context_output_reserve_tokens = max(0, agent.llm_output_reserve_tokens)

    agent.memory_consolidation.provider = provider
    refresh_consolidator_llm(agent.user_profile_update.consolidator, provider)
    refresh_consolidator_llm(agent.recent_summary_update.consolidator, provider)

    logger.info(
        "LLM runtime reloaded | provider={} model={} configured={}",
        config.llm.default or "default",
        provider.get_default_model(),
        agent.llm_configured,
    )
    return {
        "provider_id": config.llm.default,
        "model": provider.get_default_model(),
        "configured": agent.llm_configured,
        "context_window_tokens": agent.llm_context_window_tokens,
    }


def reload_agent_media_from_config(
    agent: Any,
    config: Config,
    *,
    media_router_reloader: MediaRouterReloader,
) -> dict[str, Any]:
    """Reload media analysis providers from an already persisted Config."""
    agent.media_router = media_router_reloader(agent.media_router, config)
    status = media_router_status(agent.media_router)

    logger.info(
        "Media runtime reloaded | vision={} ocr={} speech={} video={}",
        status["vision_enabled"],
        status["ocr_enabled"],
        status["speech_enabled"],
        status["video_enabled"],
    )
    return status


def reload_agent_web_search_from_config(
    agent: Any,
    config: Config,
    *,
    tool_reloader: WebSearchToolReloader,
) -> dict[str, Any]:
    """Reload web search settings and update registered web tools in-place."""
    web_search_config = config.tools.web_search
    agent.tools_config.web_search = web_search_config
    tool_reload = tool_reloader(
        agent.tools,
        web_search_config,
    )

    logger.info(
        "Web search tools reloaded | provider={} freshness={} max_results={}",
        web_search_config.provider,
        web_search_config.freshness,
        web_search_config.max_results,
    )
    return {
        "provider": web_search_config.provider,
        "freshness": web_search_config.freshness,
        "max_results": web_search_config.max_results,
        "searxng_max_pages": web_search_config.searxng_max_pages,
        "searxng_engines": list(web_search_config.searxng_engines),
        "searxng_categories": list(web_search_config.searxng_categories),
        **tool_reload,
    }


def reload_agent_browser_from_config(
    agent: Any,
    config: Config,
    *,
    tool_reloader: BrowserToolReloader,
) -> dict[str, Any]:
    """Reload browser automation settings and update registered browser tools in-place."""
    browser_config = config.tools.browser
    agent.tools_config.browser = browser_config

    tool_reload = tool_reloader(
        agent.tools,
        get_session_id=agent._get_current_session_id,
        tools_config=agent.tools_config,
    )

    logger.info(
        "Browser tools reloaded | enabled={} backend={} updated={} removed={}",
        browser_config.enabled,
        browser_config.backend,
        tool_reload["tool_updated"],
        tool_reload["tool_removed"],
    )
    return {
        "enabled": browser_config.enabled,
        "backend": browser_config.backend,
        "command_timeout": browser_config.command_timeout,
        "session_timeout": browser_config.session_timeout,
        "launch_args": browser_config.launch_args,
        **tool_reload,
    }
