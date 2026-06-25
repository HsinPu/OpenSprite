"""Service runtime for starting the OpenSprite gateway process."""

import asyncio
from pathlib import Path

from .agent.factory import create_agent
from .config import Config
from .network_environment import apply_network_environment
from .search.queue_worker import start_search_queue_worker
from .runtime_lifecycle import (
    await_shutdown_step,
    install_shutdown_signal_handlers,
    stop_background_task,
)
from .utils.log import logger


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
