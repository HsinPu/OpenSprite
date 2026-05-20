"""
opensprite/utils/log.py - 日誌模組

功能：
- 每日輪轉日誌檔案
- 自動清理過期日誌（可設定保留天數）
- 同時輸出到檔案和螢幕

日誌位置：~/.opensprite/logs/opensprite-YYYY-MM-DD.log
"""

from pathlib import Path
from loguru import logger
import sys

# 日誌目錄
LOG_DIR = Path.home() / ".opensprite" / "logs"

# 移除預設的 stderr 輸出（我們會自己加）
logger.remove()

# 追蹤是否已初始化
_initialized = False
_current_signature = None


def setup_log(config=None, console: bool = True, app_home: str | Path | None = None):
    """
    初始化日誌

    參數：
        config: LogConfig 物件，若為 None 则使用預設值
        console: 是否輸出到螢幕，預設 True
    """
    global _initialized, _current_signature

    enabled = True if config is None else bool(getattr(config, "enabled", True))
    if config:
        retention = f"{getattr(config, 'retention_days', 365)} days"
        level = str(getattr(config, "level", "INFO") or "INFO").upper()
    else:
        retention = "365 days"
        level = "INFO"

    log_dir = (Path(app_home).expanduser() if app_home is not None else Path.home() / ".opensprite") / "logs"
    signature = (enabled, retention, level, console, str(log_dir))
    if _initialized and _current_signature == signature:
        return logger
    logger.remove()
    if not enabled:
        _initialized = True
        _current_signature = signature
        return logger

    log_dir.mkdir(parents=True, exist_ok=True)

    # 設定輸出到檔案
    logger.add(
        log_dir / "opensprite-{time:YYYY-MM-DD}.log",
        rotation="1 day",           # 每日新檔案
        retention=retention,        # 保留天數
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level=level,
    )
    
    # 設定輸出到螢幕（可選，簡化格式）
    if console:
        logger.add(
            sys.stderr,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            level=level,
            colorize=True,
        )
    
    _initialized = True
    _current_signature = signature
    
    return logger


__all__ = ["logger", "setup_log"]
