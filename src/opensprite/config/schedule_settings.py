"""Shared scheduling settings helpers for Web settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .json_files import load_json_dict, write_json_dict
from .schema import Config


class ScheduleSettingsError(Exception):
    """Base error for scheduling settings operations."""


class ScheduleSettingsValidationError(ScheduleSettingsError):
    """Raised when a request is malformed."""


class ScheduleSettingsNotFound(ScheduleSettingsError):
    """Raised when scheduling settings cannot be loaded."""


COMMON_TIMEZONES = (
    "UTC",
    "Asia/Taipei",
    "Asia/Tokyo",
    "America/Los_Angeles",
    "America/New_York",
    "Europe/London",
)


def _coerce_timezone(value: Any) -> str:
    timezone = str(value or "").strip() or "UTC"
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ScheduleSettingsValidationError(f"Unknown timezone: {timezone}") from exc
    return timezone


class ScheduleSettingsService:
    """Read and mutate cron scheduling settings on disk."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).expanduser().resolve()

    def _load_main_data(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise ScheduleSettingsNotFound(f"Config file not found: {self.config_path}")
        return load_json_dict(self.config_path)

    def _payload(self, default_timezone: str) -> dict[str, Any]:
        return {
            "default_timezone": default_timezone,
            "common_timezones": list(COMMON_TIMEZONES),
            "config_path": str(self.config_path),
            "restart_required": False,
        }

    def get_schedule(self) -> dict[str, Any]:
        """Return scheduling settings."""
        if not self.config_path.exists():
            raise ScheduleSettingsNotFound(f"Config file not found: {self.config_path}")
        loaded = Config.from_json(self.config_path)
        return self._payload(_coerce_timezone(loaded.tools.cron.default_timezone))

    def update_schedule(self, *, default_timezone: str | None) -> dict[str, Any]:
        """Persist scheduling settings."""
        normalized_timezone = _coerce_timezone(default_timezone)
        main_data = self._load_main_data()
        tools = main_data.setdefault("tools", {})
        if not isinstance(tools, dict):
            raise ScheduleSettingsValidationError("tools config must be an object")
        cron = tools.setdefault("cron", {})
        if not isinstance(cron, dict):
            raise ScheduleSettingsValidationError("tools.cron config must be an object")

        cron["default_timezone"] = normalized_timezone
        write_json_dict(self.config_path, main_data)
        payload = self._payload(normalized_timezone)
        payload.update({"ok": True, "restart_required": True})
        return payload
