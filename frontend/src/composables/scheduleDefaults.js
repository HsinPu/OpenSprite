export const DEFAULT_CRON_TIMEZONE = "UTC";

export function createDefaultScheduleState() {
  return {
    default_timezone: DEFAULT_CRON_TIMEZONE,
    common_timezones: [],
  };
}

export function createDefaultScheduleForm() {
  return {
    defaultTimezone: DEFAULT_CRON_TIMEZONE,
  };
}
