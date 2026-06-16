import { normalizeNetworkSettings } from "./networkDefaults";

function syncNetworkForm(settingsState) {
  settingsState.networkForm.httpProxy = settingsState.network.http_proxy;
  settingsState.networkForm.httpsProxy = settingsState.network.https_proxy;
  settingsState.networkForm.noProxy = settingsState.network.no_proxy;
}

export function useNetworkSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }) {
  async function loadNetworkSettings() {
    settingsState.networkLoading = true;
    settingsState.networkError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/network");
      settingsState.network = normalizeNetworkSettings(payload.network || {});
      syncNetworkForm(settingsState);
    } catch (error) {
      settingsState.networkError = error?.message || copy.value.notices.networkLoadFailed;
    } finally {
      settingsState.networkLoading = false;
    }
  }

  async function saveNetworkSettings() {
    settingsState.networkLoading = true;
    settingsState.networkError = "";
    settingsState.networkNotice = "";
    try {
      const payload = await requestSettingsJson("/api/settings/network", {
        method: "PUT",
        body: JSON.stringify({
          http_proxy: settingsState.networkForm.httpProxy,
          https_proxy: settingsState.networkForm.httpsProxy,
          no_proxy: settingsState.networkForm.noProxy,
        }),
      });
      settingsState.network = normalizeNetworkSettings(payload.network || {});
      syncNetworkForm(settingsState);
      setSettingsSuccess("networkNotice", copy.value.notices.networkSaved);
    } catch (error) {
      settingsState.networkError = error?.message || copy.value.notices.networkSaveFailed;
    } finally {
      settingsState.networkLoading = false;
    }
  }

  return {
    loadNetworkSettings,
    saveNetworkSettings,
  };
}
