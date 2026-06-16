export function useUpdateSettingsActions({ settingsState, requestSettingsJson, copy }) {
  async function loadUpdateStatus() {
    settingsState.updateLoading = true;
    settingsState.updateError = "";
    try {
      settingsState.updateStatus = await requestSettingsJson("/api/settings/update");
    } catch (error) {
      settingsState.updateError = error?.message || copy.value.notices.updateStatusFailed;
    } finally {
      settingsState.updateLoading = false;
    }
  }

  async function runUpdate() {
    settingsState.updateLoading = true;
    settingsState.updateError = "";
    settingsState.updateNotice = "";
    try {
      const payload = await requestSettingsJson("/api/settings/update", {
        method: "POST",
        body: JSON.stringify({ restart: true }),
      });
      settingsState.updateStatus = {
        ...settingsState.updateStatus,
        update_available: false,
        commits_behind: 0,
        current_rev_short: payload.after_rev_short || settingsState.updateStatus.current_rev_short,
      };
      settingsState.updateNotice = payload.restart_scheduled
        ? copy.value.notices.updateRestarting
        : copy.value.notices.updateApplied;
      if (payload.restart_scheduled) {
        window.setTimeout(() => window.location.reload(), 5000);
      }
    } catch (error) {
      settingsState.updateError = error?.message || copy.value.notices.updateFailed;
    } finally {
      settingsState.updateLoading = false;
    }
  }

  return {
    loadUpdateStatus,
    runUpdate,
  };
}
