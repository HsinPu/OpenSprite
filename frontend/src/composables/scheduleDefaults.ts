export const DEFAULT_CRON_TIMEZONE = "UTC";
export const CRON_JOB_MODES = ["cron", "every", "at"] as const;
export const CRON_JOB_ACTIONS = ["pause", "enable", "run", "remove"] as const;
export type CronJobMode = (typeof CRON_JOB_MODES)[number];
export type CronJobAction = (typeof CRON_JOB_ACTIONS)[number];
const CRON_JOB_MODE_SET: ReadonlySet<string> = new Set(CRON_JOB_MODES);

function isCronJobMode(value: string): value is CronJobMode {
  return CRON_JOB_MODE_SET.has(value);
}

export function normalizeCronJobMode(value: unknown): CronJobMode {
  const normalized = String(value || "").trim().toLowerCase();
  return isCronJobMode(normalized) ? normalized : "cron";
}

export interface ScheduleState {
  default_timezone: string;
  common_timezones: string[];
}

export interface ScheduleForm {
  defaultTimezone: string;
}

export function createDefaultScheduleState(): ScheduleState {
  return {
    default_timezone: DEFAULT_CRON_TIMEZONE,
    common_timezones: [],
  };
}

export function createDefaultScheduleForm(): ScheduleForm {
  return {
    defaultTimezone: DEFAULT_CRON_TIMEZONE,
  };
}
