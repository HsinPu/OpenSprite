"""Runtime config reload helpers for AgentLoop."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..llms import LLMProvider
from ..llms.runtime_provider import create_llm_from_runtime, resolve_provider_runtime
from ..media import (
    MediaRouter,
    OpenAICompatibleSpeechProvider,
    OpenAICompatibleVideoProvider,
    create_image_analysis_provider,
)
from ..tool_names import WEB_RESEARCH_TOOL_NAME, WEB_SEARCH_TOOL_NAME
from ..tools.registration import BROWSER_TOOL_NAMES, register_browser_tools
from ..tools.web_research import WebResearchTool
from ..tools.web_search import WebSearchTool
from ..utils.log import logger


def refresh_consolidator_llm(consolidator: Any | None, provider: LLMProvider) -> None:
    """Point optional background document consolidators at the active LLM."""
    if consolidator is None:
        return
    if hasattr(consolidator, "provider"):
        consolidator.provider = provider
    if hasattr(consolidator, "model"):
        consolidator.model = provider.get_default_model()


def reload_agent_llm_from_config(agent: Any, config: Config) -> dict[str, Any]:
    """Reload the active chat LLM from an already persisted Config."""
    cfg = config.llm.get_active()
    llm_runtime = resolve_provider_runtime(
        cfg,
        provider_name=cfg.provider or config.llm.default or "",
        app_home=config.source_path.parent if config.source_path is not None else agent.app_home,
    )
    provider = create_llm_from_runtime(llm_runtime)

    agent.provider = provider
    agent.llm_output_reserve_tokens = config.agent.context_output_reserve_tokens
    agent.llm_context_window_tokens = llm_runtime.context_window_tokens
    agent.llm_configured = config.is_llm_configured
    agent.task_planner.llm_config = config.agent.task_planner_llm
    agent.completion_gate.llm_config = config.agent.completion_verifier_llm

    agent.prompt_budget.provider = provider
    agent.execution_engine.provider = provider
    agent.execution_engine.context_compaction_token_budget = agent._effective_context_token_budget()
    agent.execution_engine.context_window_tokens = agent.llm_context_window_tokens
    agent.execution_engine.context_output_reserve_tokens = max(0, agent.llm_output_reserve_tokens)

    agent.memory_consolidation.provider = provider
    refresh_consolidator_llm(agent.user_profile_update.consolidator, provider)
    refresh_consolidator_llm(agent.recent_summary_update.consolidator, provider)
    refresh_consolidator_llm(agent.active_task_update.consolidator, provider)

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


def reload_agent_media_from_config(agent: Any, config: Config) -> dict[str, Any]:
    """Reload media analysis providers from an already persisted Config."""
    vision = getattr(config, "vision", None)
    ocr = getattr(config, "ocr", None)
    speech = getattr(config, "speech", None)
    video = getattr(config, "video", None)

    if agent.media_router is None:
        agent.media_router = MediaRouter()

    agent.media_router.image_provider = (
        create_image_analysis_provider(
            provider=vision.provider,
            api_key=vision.api_key,
            default_model=vision.model,
            base_url=vision.base_url,
        )
        if vision and vision.enabled
        else None
    )
    agent.media_router.ocr_provider = (
        create_image_analysis_provider(
            provider=ocr.provider,
            api_key=ocr.api_key,
            default_model=ocr.model,
            base_url=ocr.base_url,
        )
        if ocr and ocr.enabled
        else None
    )
    agent.media_router.speech_provider = (
        OpenAICompatibleSpeechProvider(
            api_key=speech.api_key,
            default_model=speech.model,
            base_url=speech.base_url,
        )
        if speech and speech.enabled
        else None
    )
    agent.media_router.video_provider = (
        OpenAICompatibleVideoProvider(
            api_key=video.api_key,
            default_model=video.model,
            base_url=video.base_url,
        )
        if video and video.enabled
        else None
    )

    logger.info(
        "Media runtime reloaded | vision={} ocr={} speech={} video={}",
        bool(agent.media_router.image_provider),
        bool(agent.media_router.ocr_provider),
        bool(agent.media_router.speech_provider),
        bool(agent.media_router.video_provider),
    )
    return {
        "vision_enabled": bool(agent.media_router.image_provider),
        "ocr_enabled": bool(agent.media_router.ocr_provider),
        "speech_enabled": bool(agent.media_router.speech_provider),
        "video_enabled": bool(agent.media_router.video_provider),
    }


def reload_agent_web_search_from_config(agent: Any, config: Config) -> dict[str, Any]:
    """Reload web search settings and update registered web tools in-place."""
    web_search_config = config.tools.web_search
    agent.tools_config.web_search = web_search_config
    agent.tools.register(WebSearchTool(config=web_search_config))

    research_tool_updated = False
    web_research_tool = agent.tools.get(WEB_RESEARCH_TOOL_NAME)
    if isinstance(web_research_tool, WebResearchTool):
        web_research_tool.search_config = web_search_config
        if not web_research_tool._custom_search_tool:
            web_research_tool.search_tool = WebSearchTool(config=web_search_config)
        research_tool_updated = True

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
        "tool_updated": agent.tools.get(WEB_SEARCH_TOOL_NAME) is not None,
        "research_tool_updated": research_tool_updated,
    }


def reload_agent_browser_from_config(agent: Any, config: Config) -> dict[str, Any]:
    """Reload browser automation settings and update registered browser tools in-place."""
    browser_config = config.tools.browser
    agent.tools_config.browser = browser_config

    removed_tools = [name for name in BROWSER_TOOL_NAMES if agent.tools.unregister(name) is not None]
    if browser_config.enabled:
        register_browser_tools(
            agent.tools,
            get_session_id=agent._get_current_session_id,
            tools_config=agent.tools_config,
        )
    registered_tools = [name for name in BROWSER_TOOL_NAMES if agent.tools.get(name) is not None]

    logger.info(
        "Browser tools reloaded | enabled={} backend={} registered={} removed={}",
        browser_config.enabled,
        browser_config.backend,
        len(registered_tools),
        len(removed_tools),
    )
    return {
        "enabled": browser_config.enabled,
        "backend": browser_config.backend,
        "command_timeout": browser_config.command_timeout,
        "session_timeout": browser_config.session_timeout,
        "launch_args": browser_config.launch_args,
        "tool_updated": bool(registered_tools),
        "tool_removed": bool(removed_tools),
    }
