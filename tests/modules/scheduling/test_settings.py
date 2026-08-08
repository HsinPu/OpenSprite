import json

import pytest

from opensprite.config.schema import Config
from opensprite.modules.scheduling.settings import (
    COMMON_TIMEZONES,
    ScheduleSettingsNotFound,
    ScheduleSettingsService,
    ScheduleSettingsValidationError,
)


def test_schedule_settings_roundtrip_updates_only_cron_timezone(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.load(config_path)
    service = ScheduleSettingsService(config_path)

    initial = service.get_schedule()
    updated = service.update_schedule(default_timezone="Asia/Taipei")
    stored = json.loads(config_path.read_text(encoding="utf-8"))

    assert initial["default_timezone"] == "UTC"
    assert initial["common_timezones"] == list(COMMON_TIMEZONES)
    assert initial["restart_required"] is False
    assert updated["default_timezone"] == "Asia/Taipei"
    assert updated["ok"] is True
    assert updated["restart_required"] is True
    assert stored["tools"]["cron"]["default_timezone"] == "Asia/Taipei"


def test_schedule_settings_rejects_unknown_timezone(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.load(config_path)

    with pytest.raises(ScheduleSettingsValidationError, match="Unknown timezone"):
        ScheduleSettingsService(config_path).update_schedule(default_timezone="Not/AZone")


def test_schedule_settings_reports_missing_config(tmp_path):
    service = ScheduleSettingsService(tmp_path / "missing.json")

    with pytest.raises(ScheduleSettingsNotFound, match="Config file not found"):
        service.get_schedule()


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        ("tools", "tools config must be an object"),
        ("cron", "tools.cron config must be an object"),
    ],
)
def test_schedule_settings_rejects_non_object_sections(tmp_path, section, expected):
    config_path = tmp_path / "opensprite.json"
    Config.load(config_path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if section == "tools":
        data["tools"] = []
    else:
        data.setdefault("tools", {})["cron"] = []
    config_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ScheduleSettingsValidationError, match=expected):
        ScheduleSettingsService(config_path).update_schedule(default_timezone="UTC")
