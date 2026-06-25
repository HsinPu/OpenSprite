"""Process-level network environment helpers."""

from __future__ import annotations

import os

from .config import Config
from .utils.log import logger


def apply_network_environment(config: Config, *, clear_blank: bool = False) -> None:
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
        elif clear_blank:
            os.environ.pop(key, None)
            os.environ.pop(key.lower(), None)

    if values["HTTP_PROXY"] or values["HTTPS_PROXY"]:
        logger.info("Applied network proxy settings for outbound API requests")
