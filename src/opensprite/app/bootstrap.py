"""Agent runtime factory."""

from __future__ import annotations

from .messaging.dispatcher import MessageQueue
from ..config import Config
from .llm.runtime_provider import DefaultLlmRuntimeFactory, is_llm_configured
from .llm_fallback import UnconfiguredLLM
from .media import create_media_router, reload_media_router
from opensprite.core.logging import logger
from .agent.agent import AgentLoop
from .tools.registration import (
    register_memory_tool,
    reload_browser_tools,
    reload_web_search_tools,
)
from .tools.setup import register_default_agent_tools
from .search import create_history_search_store
from .scheduling import create_cron_manager
from .storage import create_storage


async def create_agent(config: Config):
    """Create the agent, message queue, and cron manager."""

    llm_runtime_factory = DefaultLlmRuntimeFactory()
    llm_configured = is_llm_configured(config)
    if llm_configured:
        llm, llm_runtime = llm_runtime_factory.create_configured(config)
    else:
        llm_runtime = None
        llm = UnconfiguredLLM()

    storage = create_storage(config)
    history_search_store = create_history_search_store(config)
    media_router = create_media_router(config)
    if history_search_store is not None:
        try:
            await history_search_store.sync_from_storage()
        except Exception as e:
            logger.warning("History search sync failed; continuing without it: {}", e)
            history_search_store = None

    agent = AgentLoop(
        config.agent,
        llm,
        storage,
        memory_config=config.memory,
        tools_config=config.tools,
        llm_output_reserve_tokens=config.agent.context_output_reserve_tokens,
        llm_context_window_tokens=llm_runtime.context_window_tokens if llm_runtime is not None else None,
        log_config=config.log,
        history_search_store=history_search_store,
        history_search_config=config.history_search,
        user_profile_config=config.user_profile,
        recent_summary_config=config.recent_summary,
        cron_manager=None,
        media_router=media_router,
        config_path=config.source_path,
        llm_config=config.llm,
        llm_configured=llm_configured,
        messages_config=config.messages,
        media_router_reloader=reload_media_router,
        llm_runtime_factory=llm_runtime_factory,
        default_tool_registrar=register_default_agent_tools,
        memory_tool_registrar=register_memory_tool,
        web_search_tool_reloader=reload_web_search_tools,
        browser_tool_reloader=reload_browser_tools,
    )
    mq = MessageQueue(agent)
    agent._message_bus = mq.bus
    cron_manager = create_cron_manager(config, agent, mq)
    agent.cron_manager = cron_manager
    cron_tool = agent.tools.get("cron")
    if cron_tool is not None:
        cron_tool.set_cron_manager(cron_manager)

    return agent, mq, cron_manager
