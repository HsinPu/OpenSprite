import { DEFAULT_CRON_TIMEZONE } from "./scheduleDefaults";

export function useScheduleSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }) {
  async function loadScheduleSettings() {
    settingsState.scheduleLoading = true;
    settingsState.scheduleError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/schedule");
      settingsState.schedule = payload;
      settingsState.scheduleForm.defaultTimezone = payload.default_timezone || DEFAULT_CRON_TIMEZONE;
      if (!settingsState.cronJobForm.timezone || !settingsState.cronJobForm.jobId) {
        settingsState.cronJobForm.timezone = settingsState.scheduleForm.defaultTimezone;
      }
    } catch (error) {
      settingsState.scheduleError = error?.message || copy.value.notices.scheduleLoadFailed;
    } finally {
      settingsState.scheduleLoading = false;
    }
  }

  async function saveScheduleSettings() {
    const defaultTimezone = String(settingsState.scheduleForm.defaultTimezone || "").trim() || DEFAULT_CRON_TIMEZONE;
    settingsState.scheduleLoading = true;
    settingsState.scheduleError = "";
    settingsState.scheduleNotice = "";
    try {
      const payload = await requestSettingsJson("/api/settings/schedule", {
        method: "PUT",
        body: JSON.stringify({ default_timezone: defaultTimezone }),
      });
      settingsState.schedule = payload;
      settingsState.scheduleForm.defaultTimezone = payload.default_timezone || defaultTimezone;
      setSettingsSuccess(
        "scheduleNotice",
        payload.restart_required
          ? copy.value.notices.scheduleRestartRequired
          : copy.value.notices.scheduleSaved(settingsState.scheduleForm.defaultTimezone),
      );
    } catch (error) {
      settingsState.scheduleError = error?.message || copy.value.notices.scheduleSaveFailed;
    } finally {
      settingsState.scheduleLoading = false;
    }
  }

  return {
    loadScheduleSettings,
    saveScheduleSettings,
  };
}
