import { normalizeNetworkSettings, type NetworkForm, type NetworkState } from "./networkDefaults";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type NetworkSettingsPayload = {
  network?: unknown;
};

interface NetworkSettingsState {
  networkLoading: boolean;
  networkError: string;
  networkNotice: string;
  network: NetworkState;
  networkForm: NetworkForm;
}

interface NetworkSettingsCopy {
  notices: {
    networkLoadFailed: string;
    networkSaved: string;
    networkSaveFailed: string;
  };
}

type SettingsActionContext = {
  settingsState: NetworkSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: NetworkSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function toNetworkSettingsPayload(value: unknown): NetworkSettingsPayload {
  const payload = toPayloadSource<NetworkSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    network: payload.network,
  };
}

function syncNetworkForm(settingsState: NetworkSettingsState): void {
  settingsState.networkForm.httpProxy = settingsState.network.http_proxy;
  settingsState.networkForm.httpsProxy = settingsState.network.https_proxy;
  settingsState.networkForm.noProxy = settingsState.network.no_proxy;
}

export function useNetworkSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }: SettingsActionContext) {
  async function loadNetworkSettings(): Promise<void> {
    settingsState.networkLoading = true;
    settingsState.networkError = "";
    try {
      const payload = toNetworkSettingsPayload(await requestSettingsJson("/api/settings/network"));
      settingsState.network = normalizeNetworkSettings(payload.network);
      syncNetworkForm(settingsState);
    } catch (error: unknown) {
      settingsState.networkError = errorMessage(error) || copy.value.notices.networkLoadFailed;
    } finally {
      settingsState.networkLoading = false;
    }
  }

  async function saveNetworkSettings(): Promise<void> {
    settingsState.networkLoading = true;
    settingsState.networkError = "";
    settingsState.networkNotice = "";
    try {
      const payload = toNetworkSettingsPayload(await requestSettingsJson("/api/settings/network", {
        method: "PUT",
        body: JSON.stringify({
          http_proxy: settingsState.networkForm.httpProxy,
          https_proxy: settingsState.networkForm.httpsProxy,
          no_proxy: settingsState.networkForm.noProxy,
        }),
      }));
      settingsState.network = normalizeNetworkSettings(payload.network);
      syncNetworkForm(settingsState);
      setSettingsSuccess("networkNotice", copy.value.notices.networkSaved);
    } catch (error: unknown) {
      settingsState.networkError = errorMessage(error) || copy.value.notices.networkSaveFailed;
    } finally {
      settingsState.networkLoading = false;
    }
  }

  return {
    loadNetworkSettings,
    saveNetworkSettings,
  };
}
