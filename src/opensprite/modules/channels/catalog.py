"""Pure metadata and configuration policies for supported channel types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...config.channel_instances import DEFAULT_WEB_CHANNEL_CONFIG
from ...core.contracts.channel_identity import normalize_identifier


@dataclass(frozen=True)
class ChannelTypeSpec:
    """Metadata for one supported channel type."""

    type_id: str
    name: str
    description: str
    secret_fields: frozenset[str] = frozenset()
    default_config: dict[str, Any] = field(default_factory=dict)
    requires_token: bool = False


CHANNEL_TYPES: dict[str, ChannelTypeSpec] = {
    "telegram": ChannelTypeSpec(
        type_id="telegram",
        name="Telegram",
        description="透過 Telegram bot 收發聊天訊息。",
        secret_fields=frozenset({"token"}),
        requires_token=True,
        default_config={
            "enabled": True,
            "token": "",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "pool_timeout": 30,
            "get_updates_connect_timeout": 10,
            "get_updates_read_timeout": 30,
            "get_updates_write_timeout": 30,
            "get_updates_pool_timeout": 30,
            "poll_timeout": 10,
            "bootstrap_retries": 3,
            "drop_pending_updates": False,
        },
    ),
    "web": ChannelTypeSpec(
        type_id="web",
        name="Web",
        description="瀏覽器 WebSocket 頻道與設定介面。",
        default_config=dict(DEFAULT_WEB_CHANNEL_CONFIG),
    ),
}


def get_channel_type(type_id: str) -> ChannelTypeSpec | None:
    return CHANNEL_TYPES.get(normalize_identifier(type_id, fallback=""))


def list_connectable_channel_types() -> list[ChannelTypeSpec]:
    return [CHANNEL_TYPES[type_id] for type_id in ("telegram",)]


def default_instance_config(channel_type: str, *, name: str | None = None) -> dict[str, Any]:
    spec = get_channel_type(channel_type)
    if spec is None:
        raise KeyError(channel_type)
    return {"type": spec.type_id, "name": name or spec.name, **dict(spec.default_config)}


def make_unique_instance_id(
    instances: dict[str, Any],
    channel_type: str,
    name: str | None = None,
) -> str:
    base = normalize_identifier(name, fallback=channel_type)
    if not base.startswith(channel_type):
        base = f"{channel_type}_{base}"
    candidate = base
    index = 2
    while candidate in instances:
        candidate = f"{base}_{index}"
        index += 1
    return candidate
