import { providerCredentialEndpoint, providerSettingsEndpoint } from "../settings/providerConstants";
import { loadProviderSettingsState } from "./providerSettingsLoader";
import { runProviderMutation } from "./providerMutationRunner";
import {
  createProviderConnectForm,
  providerConnectPayloadFromForm,
  providerCredentialKey,
  providerCredentialPayload,
} from "./providerConnectForm";

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
    await runProviderMutation(settingsState, copy.value.notices.providerConnectFailed, async () => {
      await requestSettingsJson(providerSettingsEndpoint(providerId, "connect"), {
        method: "PUT",
        body: JSON.stringify(providerConnectPayloadFromForm(settingsState.connectForm)),
      });
      setSettingsSuccess("providersNotice", copy.value.notices.providerConnected);
      cancelProviderConnect();
      await refreshProviderState();
    });
  }

  async function disconnectProvider(provider) {
    await runProviderMutation(settingsState, copy.value.notices.providerDisconnectFailed, async () => {
      const payload = await requestSettingsJson(providerSettingsEndpoint(provider.id, "disconnect"), {
        method: "POST",
      });
      setSettingsSuccess("providersNotice", copy.value.notices.providerDisconnected(provider.name, payload.restart_required));
      await refreshProviderState();
    });
  }

  async function setProviderCredential(provider, credentialId) {
    if (!provider?.id || !credentialId || credentialId === provider.credential_id) {
      return;
    }
    await runProviderMutation(settingsState, copy.value.notices.providerCredentialUpdateFailed, async () => {
      const payload = await requestSettingsJson(providerSettingsEndpoint(provider.id, "credential"), {
        method: "POST",
        body: JSON.stringify(providerCredentialPayload(credentialId)),
      });
      setSettingsSuccess("providersNotice", copy.value.notices.providerCredentialUpdated(payload.restart_required));
      await refreshProviderState();
    });
  }

  async function deleteCredential(provider, credentialId) {
    const providerKey = providerCredentialKey(provider);
    if (!providerKey || !credentialId) {
      return;
    }
    await runProviderMutation(settingsState, copy.value.notices.providerCredentialDeleteFailed, async () => {
      await requestSettingsJson(
        providerCredentialEndpoint(providerKey, credentialId),
        { method: "DELETE" },
      );
      setSettingsSuccess("providersNotice", copy.value.notices.providerCredentialDeleted);
      await refreshProviderState();
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
