import { DEFAULT_LOG_LEVEL, DEFAULT_LOG_REASONING_DETAILS, DEFAULT_LOG_RETENTION_DAYS, DEFAULT_LOG_SYSTEM_PROMPT_LINES, normalizeLogSettings } from "./logDefaults";

function syncLogForm(settingsState) {
  settingsState.logForm.enabled = Boolean(settingsState.log.enabled);
  settingsState.logForm.level = settingsState.log.level || DEFAULT_LOG_LEVEL;
  settingsState.logForm.retentionDays = Number(settingsState.log.retention_days || DEFAULT_LOG_RETENTION_DAYS);
  settingsState.logForm.logSystemPrompt = Boolean(settingsState.log.log_system_prompt);
  settingsState.logForm.logSystemPromptLines = Number(settingsState.log.log_system_prompt_lines || DEFAULT_LOG_SYSTEM_PROMPT_LINES);
  settingsState.logForm.logReasoningDetails = Boolean(settingsState.log.log_reasoning_details || DEFAULT_LOG_REASONING_DETAILS);
}

export function useLogSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }) {
  async function loadLogSettings() {
    settingsState.logLoading = true;
    settingsState.logError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/log");
      settingsState.log = normalizeLogSettings(payload.log || {});
      syncLogForm(settingsState);
    } catch (error) {
      settingsState.logError = error?.message || copy.value.notices.logLoadFailed;
    } finally {
      settingsState.logLoading = false;
    }
  }

  async function saveLogSettings() {
    settingsState.logLoading = true;
    settingsState.logError = "";
    settingsState.logNotice = "";
    try {
      const payload = await requestSettingsJson("/api/settings/log", {
        method: "PUT",
        body: JSON.stringify({
          enabled: Boolean(settingsState.logForm.enabled),
          level: settingsState.logForm.level || DEFAULT_LOG_LEVEL,
          retention_days: Number(settingsState.logForm.retentionDays || DEFAULT_LOG_RETENTION_DAYS),
          log_system_prompt: Boolean(settingsState.logForm.logSystemPrompt),
          log_system_prompt_lines: Number(settingsState.logForm.logSystemPromptLines || DEFAULT_LOG_SYSTEM_PROMPT_LINES),
          log_reasoning_details: Boolean(settingsState.logForm.logReasoningDetails),
        }),
      });
      settingsState.log = normalizeLogSettings(payload.log || {});
      syncLogForm(settingsState);
      setSettingsSuccess("logNotice", copy.value.notices.logSaved);
    } catch (error) {
      settingsState.logError = error?.message || copy.value.notices.logSaveFailed;
    } finally {
      settingsState.logLoading = false;
    }
  }

  return {
    loadLogSettings,
    saveLogSettings,
  };
}
