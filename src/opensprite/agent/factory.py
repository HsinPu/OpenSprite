"""Agent runtime factory."""

from __future__ import annotations

from ..bus.dispatcher import MessageQueue
from ..config import Config
from ..cron.factory import create_cron_manager
from ..llms import UnconfiguredLLM
from ..llms.runtime_provider import create_llm_from_runtime, resolve_provider_runtime
from ..media.factory import create_media_router
from ..search.store_factory import create_search_store
from ..storage.factory import create_storage
from ..utils.log import logger
from .agent import AgentLoop


async def create_agent(config: Config):
    """Create the agent, message queue, and cron manager."""

    cfg = config.llm.get_active()
    if config.is_llm_configured:
        llm_runtime = resolve_provider_runtime(
            cfg,
            provider_name=cfg.provider or config.llm.default or "",
            app_home=config.source_path.parent if config.source_path is not None else None,
        )
        llm = create_llm_from_runtime(llm_runtime)
    else:
        llm_runtime = None
        llm = UnconfiguredLLM()

    storage = create_storage(config)
    search_store = create_search_store(config)
    media_router = create_media_router(config)
    if search_store is not None:
        try:
            await search_store.sync_from_storage(storage)
        except Exception as e:
            logger.warning("Search store sync failed; continuing without search: {}", e)
            search_store = None

    agent = AgentLoop(
        config.agent,
        llm,
        storage,
        memory_config=config.memory,
        tools_config=config.tools,
        llm_output_reserve_tokens=config.agent.context_output_reserve_tokens,
        llm_context_window_tokens=llm_runtime.context_window_tokens if llm_runtime is not None else None,
        log_config=config.log,
        search_store=search_store,
        search_config=config.search,
        user_profile_config=config.user_profile,
        active_task_config=config.active_task,
        recent_summary_config=config.recent_summary,
        cron_manager=None,
        media_router=media_router,
        config_path=config.source_path,
        llm_config=config.llm,
        llm_configured=config.is_llm_configured,
        messages_config=config.messages,
    )
    mq = MessageQueue(agent)
    agent._message_bus = mq.bus
    cron_manager = create_cron_manager(config, agent, mq)
    agent.cron_manager = cron_manager
    cron_tool = agent.tools.get("cron")
    if cron_tool is not None:
        cron_tool.set_cron_manager(cron_manager)

    return agent, mq, cron_manager
