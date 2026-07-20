"""Pure channel instance configuration defaults and normalization."""

from __future__ import annotations

from typing import Any


DEFAULT_WEB_CHANNEL_CONFIG: dict[str, Any] = {
    "enabled": True,
    "host": "127.0.0.1",
    "port": 8765,
    "path": "/ws",
    "health_path": "/healthz",
    "max_message_size": 1024 * 1024,
    "frontend_auto_build": True,
    "frontend_auto_install": True,
    "frontend_build_timeout": 120,
    "frontend_install_timeout": 300,
    "auth_token": "",
}


def default_channel_instances() -> dict[str, dict[str, Any]]:
    """Return fresh default channel instance data."""
    return {
        "web": {
            "type": "web",
            "name": "Web",
            **dict(DEFAULT_WEB_CHANNEL_CONFIG),
        }
    }


def coerce_channel_instances(channels_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize channel configuration into an instance mapping."""
    raw_instances = channels_data.get("instances")
    instances: dict[str, dict[str, Any]] = {}
    if isinstance(raw_instances, dict):
        instances = {
            str(instance_id): dict(config)
            for instance_id, config in raw_instances.items()
            if isinstance(config, dict)
        }

    if "web" not in instances:
        instances.update(default_channel_instances())
    return instances
