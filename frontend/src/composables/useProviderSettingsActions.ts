import { loadProviderSettingsState } from "./providerSettingsLoader";
import { runProviderMutation } from "./providerMutationRunner";
import {
  requestProviderConnect,
  requestProviderCredentialDelete,
  requestProviderCredentialUpdate,
  requestProviderDisconnect,
} from "./providerSettingsRequests";
import {
  createProviderConnectForm,
  type ProviderConnectForm,
  type ProviderPayload,
} from "./providerConnectForm";
import type { ProviderCredentialsState, ProviderSettings } from "./useSettingsState";
import { providerCatalogKey } from "../settings/providerHelpers";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;

interface ProviderSettingsState {
  providersLoading: boolean;
  providersError: string;
  providersNotice: string;
  providers: ProviderSettings;
  credentials: ProviderCredentialsState;
  connectForm: ProviderConnectForm;
}

interface ProviderSettingsCopy {
  notices: {
    providerLoadFailed: string;
    providerConnectFailed: string;
    providerConnected: string;
    providerDisconnectFailed: string;
    providerDisconnected: (name: string, restartRequired: boolean) => string;
    providerCredentialUpdateFailed: string;
    providerCredentialUpdated: (restartRequired: boolean) => string;
    providerCredentialDeleteFailed: string;
    providerCredentialDeleted: string;
  };
}

type ProviderSettingsActionsContext = {
  settingsState: ProviderSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: ProviderSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
  cancelChannelConnect: () => void;
  cancelProviderConnect: () => void;
  loadModelSettings: () => Promise<void>;
};

function optionalText(value: unknown): string {
  return String(value || "").trim();
}

function providerDisplayName(provider: ProviderPayload): string {
  return optionalText(provider.name || provider.id);
}

export function useProviderSettingsActions({
  settingsState,
  requestSettingsJson,
  copy,
  setSettingsSuccess,
  cancelChannelConnect,
  cancelProviderConnect,
  loadModelSettings,
}: ProviderSettingsActionsContext) {
  async function loadProviderSettings(): Promise<void> {
    await loadProviderSettingsState(settingsState, requestSettingsJson, copy);
  }

  async function refreshProviderState(): Promise<void> { await loadProviderSettings(); await loadModelSettings(); }

  async function runProviderSettingsMutation(fallbackNotice: string, action: () => void | Promise<void>): Promise<void> {
    await runProviderMutation(settingsState, fallbackNotice, action, { after: refreshProviderState });
  }

  function beginProviderConnect(provider: ProviderPayload): void {
    settingsState.providersNotice = "";
    settingsState.providersError = "";
    cancelChannelConnect();
    Object.assign(settingsState.connectForm, createProviderConnectForm(provider));
  }

  async function saveProviderConnection(): Promise<void> {
    const providerId = settingsState.connectForm.providerId;
    if (!providerId) {
      return;
    }
    await runProviderSettingsMutation(copy.value.notices.providerConnectFailed, async () => {
      await requestProviderConnect(requestSettingsJson, settingsState.connectForm);
      setSettingsSuccess("providersNotice", copy.value.notices.providerConnected);
      cancelProviderConnect();
    });
  }

  async function disconnectProvider(provider: ProviderPayload): Promise<void> {
    await runProviderSettingsMutation(copy.value.notices.providerDisconnectFailed, async () => {
      const payload = await requestProviderDisconnect(requestSettingsJson, provider);
      setSettingsSuccess("providersNotice", copy.value.notices.providerDisconnected(providerDisplayName(provider), Boolean(payload.restart_required)));
    });
  }

  async function setProviderCredential(provider: ProviderPayload, credentialId: string): Promise<void> {
    if (!optionalText(provider.id) || !credentialId || credentialId === optionalText(provider.credential_id)) {
      return;
    }
    await runProviderSettingsMutation(copy.value.notices.providerCredentialUpdateFailed, async () => {
      const payload = await requestProviderCredentialUpdate(requestSettingsJson, provider, credentialId);
      setSettingsSuccess("providersNotice", copy.value.notices.providerCredentialUpdated(Boolean(payload.restart_required)));
    });
  }

  async function deleteCredential(provider: ProviderPayload, credentialId: string): Promise<void> {
    const providerKey = providerCatalogKey(provider);
    if (!providerKey || !credentialId) {
      return;
    }
    await runProviderSettingsMutation(copy.value.notices.providerCredentialDeleteFailed, async () => {
      await requestProviderCredentialDelete(requestSettingsJson, providerKey, credentialId);
      setSettingsSuccess("providersNotice", copy.value.notices.providerCredentialDeleted);
    });
  }

  return {
    loadProviderSettings,
    beginProviderConnect,
    saveProviderConnection,
    disconnectProvider,
    setProviderCredential,
    deleteCredential,
  };
}
