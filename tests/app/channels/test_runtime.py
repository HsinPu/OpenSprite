import asyncio

import opensprite.app.channels.runtime as channels_runtime
from opensprite.app.channels.adapters import CHANNEL_ADAPTER_FACTORIES, build_channel_adapter
from opensprite.config.channel_instances import DEFAULT_WEB_CHANNEL_CONFIG, default_channel_instances
from opensprite.integrations.channels.telegram import TelegramAdapter
from opensprite.integrations.web.adapter import WebAdapter
from opensprite.modules.channels.catalog import CHANNEL_TYPES


class FakeAdapter:
    def __init__(self, name, started):
        self.name = name
        self.started = started

    async def run(self):
        self.started.append(self.name)


def test_start_channels_only_runs_enabled_registered_channels(monkeypatch):
    started = []

    monkeypatch.setattr(
        channels_runtime,
        "CHANNEL_FACTORIES",
        {
            "telegram": lambda mq, instance_id, cfg: FakeAdapter(instance_id, started),
            "discord": lambda mq, instance_id, cfg: FakeAdapter(instance_id, started),
        },
    )

    asyncio.run(
        channels_runtime.start_channels(
            object(),
            {
                "instances": {
                    "telegram_work": {"type": "telegram", "enabled": True},
                    "discord_team": {"type": "discord", "enabled": False},
                    "unknown_local": {"type": "unknown", "enabled": True},
                },
            },
        )
    )

    assert started == ["telegram_work"]


def test_web_channel_defaults_expose_auth_token():
    instances = default_channel_instances()

    assert instances["web"]["auth_token"] == ""
    assert CHANNEL_TYPES["web"].default_config == DEFAULT_WEB_CHANNEL_CONFIG
    assert CHANNEL_TYPES["web"].default_config is not DEFAULT_WEB_CHANNEL_CONFIG


def test_channel_catalog_matches_runtime_adapter_registry():
    assert set(CHANNEL_TYPES) == set(CHANNEL_ADAPTER_FACTORIES)


def test_channel_adapter_factory_builds_canonical_telegram_adapter():
    adapter = build_channel_adapter(
        object(),
        "telegram_work",
        {"type": "telegram", "token": "secret"},
    )

    assert isinstance(adapter, TelegramAdapter)
    assert adapter.channel_instance_id == "telegram_work"


def test_channel_adapter_factory_builds_canonical_web_adapter():
    mq = object()

    adapter = build_channel_adapter(
        mq,
        "web_dashboard",
        {"type": "web", "frontend_auto_build": False},
    )

    assert isinstance(adapter, WebAdapter)
    assert adapter.mq is mq
    assert adapter.channel_instance_id == "web_dashboard"
    assert adapter.config["id"] == "web_dashboard"
    assert adapter.config["frontend_auto_build"] is False


def test_web_adapter_factory_injects_live_channel_registration_predicate():
    adapter = build_channel_adapter(
        object(),
        "web_dashboard",
        {"type": "web", "frontend_auto_build": False},
    )

    assert isinstance(adapter, WebAdapter)
    assert adapter._is_registered_channel_type("discord") is False

    CHANNEL_ADAPTER_FACTORIES["discord"] = lambda *_args: object()
    try:
        assert adapter._is_registered_channel_type("discord") is True
    finally:
        CHANNEL_ADAPTER_FACTORIES.pop("discord", None)


def test_direct_web_adapter_uses_catalog_registration_predicate():
    adapter = WebAdapter(config={"frontend_auto_build": False})

    assert adapter._is_registered_channel_type("telegram") is True
    assert adapter._is_registered_channel_type("discord") is False
