"""Application-wide logging facade."""

from loguru import logger


# OpenSprite configures its own sinks during application startup.
logger.remove()

__all__ = ["logger"]
