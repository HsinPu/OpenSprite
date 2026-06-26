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
} from "./providerConnectForm";
import { providerCatalogKey } from "../settings/providerHelpers";

export function useProviderSettingsActions({
  settingsState,
  requestSettingsJson,
  copy,
  setSettingsSuccess,
  cancelChannelConnect,
  cancelProviderConnect,
  loadModelSettings,
}) {
  async function loadProviderSettings() {
    await loadProviderSettingsState(settingsState, requestSettingsJson, copy);
  }

  async function refreshProviderState() { await loadProviderSettings(); await loadModelSettings(); }

  async function runProviderSettingsMutation(fallbackNotice, action) {
    await runProviderMutation(settingsState, fallbackNotice, action, { after: refreshProviderState });
  }

  function beginProviderConnect(provider) {
    settingsState.providersNotice = "";
    settingsState.providersError = "";
    cancelChannelConnect();
    Object.assign(settingsState.connectForm, createProviderConnectForm(provider));
  }

  async function saveProviderConnection() {
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

  async function disconnectProvider(provider) {
    await runProviderSettingsMutation(copy.value.notices.providerDisconnectFailed, async () => {
      const payload = await requestProviderDisconnect(requestSettingsJson, provider);
      setSettingsSuccess("providersNotice", copy.value.notices.providerDisconnected(provider.name, payload.restart_required));
    });
  }

  async function setProviderCredential(provider, credentialId) {
    if (!provider?.id || !credentialId || credentialId === provider.credential_id) {
      return;
    }
    await runProviderSettingsMutation(copy.value.notices.providerCredentialUpdateFailed, async () => {
      const payload = await requestProviderCredentialUpdate(requestSettingsJson, provider, credentialId);
      setSettingsSuccess("providersNotice", copy.value.notices.providerCredentialUpdated(payload.restart_required));
    });
  }

  async function deleteCredential(provider, credentialId) {
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
