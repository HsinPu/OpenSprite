"""Channel adapter construction registry."""

from __future__ import annotations

from typing import Any, Callable

from ...core.contracts.channel_identity import normalize_identifier


AdapterFactory = Callable[[Any, str, dict[str, Any]], Any]


def _build_telegram_adapter(mq: Any, instance_id: str, channel_config: dict[str, Any]) -> Any:
    from ...integrations.channels.telegram import TelegramAdapter

    return TelegramAdapter(
        bot_token=channel_config.get("token", ""),
        mq=mq,
        config=channel_config,
        channel_instance_id=instance_id,
    )


def _build_web_adapter(mq: Any, instance_id: str, channel_config: dict[str, Any]) -> Any:
    from ...integrations.web.adapter import WebAdapter

    config = dict(channel_config)
    config.setdefault("id", instance_id)
    return WebAdapter(
        mq=mq,
        config=config,
        is_registered_channel_type=CHANNEL_ADAPTER_FACTORIES.__contains__,
    )


CHANNEL_ADAPTER_FACTORIES: dict[str, AdapterFactory] = {
    "telegram": _build_telegram_adapter,
    "web": _build_web_adapter,
}


def build_channel_adapter(mq: Any, instance_id: str, channel_config: dict[str, Any]) -> Any | None:
    channel_type = normalize_identifier(str(channel_config.get("type") or instance_id), fallback="")
    factory = CHANNEL_ADAPTER_FACTORIES.get(channel_type)
    if factory is None:
        return None
    return factory(mq, normalize_identifier(instance_id, fallback=channel_type), channel_config)
