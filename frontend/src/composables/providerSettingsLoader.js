export async function loadProviderSettingsState(settingsState, requestSettingsJson, copy) {
  settingsState.providersLoading = true;
  settingsState.providersError = "";
  try {
    const [providers, credentials] = await Promise.all([
      requestSettingsJson("/api/settings/providers"),
      requestSettingsJson("/api/settings/credentials"),
    ]);
    settingsState.providers = providers;
    settingsState.credentials = credentials.credentials || {};
  } catch (error) {
    settingsState.providersError = error?.message || copy.value.notices.providerLoadFailed;
  } finally {
    settingsState.providersLoading = false;
  }
}
