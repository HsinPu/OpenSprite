"""Channel settings registration behavior."""

from __future__ import annotations

import json

from opensprite.config.schema import Config
from opensprite.integrations.web.settings.support import get_channel_settings


class _SettingsAdapter:
    def __init__(self, config_path, *, is_registered_channel_type=None):
        self._config_path = config_path
        self._is_registered_channel_type = is_registered_channel_type

    def _get_config_path(self):
        return self._config_path


def test_adapter_registration_predicate_reports_custom_runtime_factory_as_registered(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    main_data = json.loads(config_path.read_text(encoding="utf-8"))
    Config.write_channels_file(
        config_path,
        {
            "instances": {
                "discord_team": {
                    "type": "discord",
                    "name": "Discord Team",
                    "enabled": True,
                }
            }
        },
        main_data,
    )

    payload = get_channel_settings(
        _SettingsAdapter(
            config_path,
            is_registered_channel_type=lambda channel_type: channel_type == "discord",
        )
    ).list_channels()

    assert payload["connected"] == [
        {
            "id": "discord_team",
            "instance_id": "discord_team",
            "type": "discord",
            "name": "Discord Team",
            "description": "Custom channel configuration.",
            "enabled": True,
            "registered": True,
            "token_configured": False,
            "settings": {},
        }
    ]


def test_catalog_fallback_reports_builtin_channel_type_as_registered(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    main_data = json.loads(config_path.read_text(encoding="utf-8"))
    Config.write_channels_file(
        config_path,
        {
            "instances": {
                "telegram_team": {
                    "type": "telegram",
                    "name": "Telegram Team",
                    "enabled": True,
                    "token": "test-token",
                }
            }
        },
        main_data,
    )

    payload = get_channel_settings(_SettingsAdapter(config_path)).list_channels()

    assert payload["connected"][0]["type"] == "telegram"
    assert payload["connected"][0]["registered"] is True
