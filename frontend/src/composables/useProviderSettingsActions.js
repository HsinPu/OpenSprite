import { providerCredentialEndpoint, providerSettingsEndpoint } from "../settings/providerConstants";
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
