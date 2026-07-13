import { DEFAULT_CRON_TIMEZONE, type ScheduleForm, type ScheduleState } from "./scheduleDefaults";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type ScheduleSettingsPayload = {
  default_timezone?: unknown;
  common_timezones?: unknown;
  restart_required?: unknown;
};

interface CronJobTimezoneForm {
  jobId: string;
  timezone: string;
}

interface ScheduleSettingsState {
  scheduleLoading: boolean;
  scheduleError: string;
  scheduleNotice: string;
  schedule: ScheduleState;
  scheduleForm: ScheduleForm;
  cronJobForm: CronJobTimezoneForm;
}

interface ScheduleSettingsCopy {
  notices: {
    scheduleLoadFailed: string;
    scheduleRestartRequired: string;
    scheduleSaved: (timezone: string) => string;
    scheduleSaveFailed: string;
  };
}

type SettingsActionContext = {
  settingsState: ScheduleSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: ScheduleSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function timezoneOrDefault(value: unknown, fallback = DEFAULT_CRON_TIMEZONE): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function toScheduleSettingsPayload(value: unknown): ScheduleSettingsPayload {
  const payload = toPayloadSource<ScheduleSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    default_timezone: payload.default_timezone,
    common_timezones: payload.common_timezones,
    restart_required: payload.restart_required,
  };
}

function normalizeScheduleSettings(payload: ScheduleSettingsPayload): ScheduleState {
  return {
    default_timezone: timezoneOrDefault(payload.default_timezone),
    common_timezones: Array.isArray(payload.common_timezones)
      ? payload.common_timezones.filter((timezone): timezone is string => typeof timezone === "string")
      : [],
  };
}

export function useScheduleSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }: SettingsActionContext) {
  async function loadScheduleSettings(): Promise<void> {
    settingsState.scheduleLoading = true;
    settingsState.scheduleError = "";
    try {
      const payload = toScheduleSettingsPayload(await requestSettingsJson("/api/settings/schedule"));
      settingsState.schedule = normalizeScheduleSettings(payload);
      settingsState.scheduleForm.defaultTimezone = settingsState.schedule.default_timezone;
      if (!settingsState.cronJobForm.timezone || !settingsState.cronJobForm.jobId) {
        settingsState.cronJobForm.timezone = settingsState.scheduleForm.defaultTimezone;
      }
    } catch (error: unknown) {
      settingsState.scheduleError = errorMessage(error) || copy.value.notices.scheduleLoadFailed;
    } finally {
      settingsState.scheduleLoading = false;
    }
  }

  async function saveScheduleSettings(): Promise<void> {
    const defaultTimezone = String(settingsState.scheduleForm.defaultTimezone || "").trim() || DEFAULT_CRON_TIMEZONE;
    settingsState.scheduleLoading = true;
    settingsState.scheduleError = "";
    settingsState.scheduleNotice = "";
    try {
      const payload = toScheduleSettingsPayload(await requestSettingsJson("/api/settings/schedule", {
        method: "PUT",
        body: JSON.stringify({ default_timezone: defaultTimezone }),
      }));
      settingsState.schedule = normalizeScheduleSettings({
        default_timezone: timezoneOrDefault(payload.default_timezone, defaultTimezone),
        common_timezones: payload.common_timezones,
      });
      settingsState.scheduleForm.defaultTimezone = settingsState.schedule.default_timezone;
      setSettingsSuccess(
        "scheduleNotice",
        payload.restart_required
          ? copy.value.notices.scheduleRestartRequired
          : copy.value.notices.scheduleSaved(settingsState.scheduleForm.defaultTimezone),
      );
    } catch (error: unknown) {
      settingsState.scheduleError = errorMessage(error) || copy.value.notices.scheduleSaveFailed;
    } finally {
      settingsState.scheduleLoading = false;
    }
  }

  return {
    loadScheduleSettings,
    saveScheduleSettings,
  };
}
