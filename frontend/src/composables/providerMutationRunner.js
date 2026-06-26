export async function runProviderMutation(settingsState, fallbackNotice, action, options = {}) {
  settingsState.providersLoading = true;
  settingsState.providersError = "";
  settingsState.providersNotice = "";
  options.before?.();
  try {
    await action();
  } catch (error) {
    settingsState.providersError = error?.message || fallbackNotice;
  } finally {
    settingsState.providersLoading = false;
  }
}
