"""Service runtime for starting the OpenSprite gateway process."""

import asyncio
import os
from pathlib import Path

from .agent import AgentLoop
from .config import AgentConfig
from .cron.factory import create_cron_manager
from .llms.runtime_provider import create_llm_from_runtime, resolve_provider_runtime
from .media.factory import create_media_router
from .search.embedding_factory import create_search_embedding_provider
from .search.queue_worker import should_start_search_queue_worker, start_search_queue_worker
from .search.store_factory import create_search_store
from .storage.factory import create_storage
from .bus.dispatcher import MessageQueue
from .config import Config
from .llms import UnconfiguredLLM
from .runtime_lifecycle import (
    await_shutdown_step,
    install_shutdown_signal_handlers,
    stop_background_task,
)
from .utils.log import logger


# ============================================
# 共用設定
# ============================================

def apply_network_environment(config: Config) -> None:
    """Apply configured proxy settings for urllib/httpx/OpenAI clients in this process."""
    network = getattr(config, "network", None)
    if network is None:
        return

    values = {
        "HTTP_PROXY": getattr(network, "http_proxy", "") or "",
        "HTTPS_PROXY": getattr(network, "https_proxy", "") or "",
        "NO_PROXY": getattr(network, "no_proxy", "") or "",
    }
    for key, value in values.items():
        normalized = str(value or "").strip()
        if normalized:
            os.environ[key] = normalized
            os.environ[key.lower()] = normalized

    if values["HTTP_PROXY"] or values["HTTPS_PROXY"]:
        logger.info("Applied network proxy settings for outbound API requests")


async def create_agent(config: Config):
    """建立 Agent 和 Queue"""
    # 用 Registry 建立 LLM Provider
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
    
    # 建立 Agent 設定
    agent_config = config.agent
    
    # 建立 Storage
    storage = create_storage(config)
    search_store = create_search_store(config)
    media_router = create_media_router(config)
    if search_store is not None:
        try:
            await search_store.sync_from_storage(storage)
        except Exception as e:
            logger.warning("Search store sync failed; continuing without search: {}", e)
            search_store = None
    
    # 建立 Agent
    agent = AgentLoop(
        agent_config,
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


# ============================================
# 啟動服務
# ============================================

async def run(config_path: str | Path | None = None) -> None:
    """Start the OpenSprite gateway service."""
    from .utils.log import setup_log

    # Config loading can fail before the configured log section is available.
    # Install a default sink first so fresh-install startup errors are visible.
    early_app_home = Path(config_path).expanduser().resolve().parent if config_path is not None else None
    setup_log(app_home=early_app_home)

    # 讀取設定
    config = Config.load(config_path)
    
    # 初始化日誌
    setup_log(config.log, app_home=config.source_path.parent if config.source_path is not None else early_app_home)
    apply_network_environment(config)

    if not config.is_llm_configured:
        logger.warning(
            "LLM is not configured. Gateway will still start, but agent replies will ask users to configure LLM first."
        )
    
    # 建立 Agent + MessageQueue
    agent, mq, cron_manager = await create_agent(config)
    search_queue_worker = start_search_queue_worker(getattr(agent, "search_store", None))
    background_process_manager = getattr(agent, "background_process_manager", None)
    if background_process_manager is not None:
        await background_process_manager.mark_lost_persisted_sessions()

    # 啟動前先連 MCP，讓外部 tools 在服務運行時就緒
    await agent.connect_mcp()
    await cron_manager.start()
    
    # 啟動訊息處理迴圈
    processor = asyncio.create_task(mq.process_queue())
    channel_manager = None

    try:
        # 啟動所有頻道
        from .channels import start_channels

        channel_manager = await start_channels(mq, config.channels)

        logger.info("OpenSprite gateway 啟動完成！")
        logger.info("按 Ctrl+C 停止")

        # 等待直到被中斷
        shutdown_event = asyncio.Event()
        install_shutdown_signal_handlers(shutdown_event)
        await shutdown_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("正在關閉...")
    finally:
        if channel_manager is not None:
            await await_shutdown_step(channel_manager.stop_all(), name="channel manager")
        await await_shutdown_step(mq.stop(), name="message queue")
        await stop_background_task(processor, name="message queue processor")
        await stop_background_task(search_queue_worker, name="search embedding queue worker")
        await await_shutdown_step(cron_manager.stop(), name="cron manager")
        await await_shutdown_step(agent.close_background_maintenance(), name="background maintenance")
        await await_shutdown_step(agent.close_background_skill_reviews(), name="background skill reviews")
        close_background_processes = getattr(agent, "close_background_processes", None)
        if close_background_processes is not None:
            await await_shutdown_step(close_background_processes(), name="background processes")
        await await_shutdown_step(agent.close_mcp(), name="MCP connections")
        logger.info("再見！")


# ============================================
# 主程式
# ============================================

def gateway(config_path: str | Path | None = None) -> None:
    """Run the foreground OpenSprite gateway."""
    asyncio.run(run(config_path=config_path))


if __name__ == "__main__":
    gateway()
