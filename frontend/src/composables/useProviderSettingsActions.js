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
    settingsState.connectForm.providerId = provider.id;
    settingsState.connectForm.name = provider.connected_count
      ? `${provider.name} ${provider.connected_count + 1}`
      : provider.name;
    settingsState.connectForm.apiKey = "";
    settingsState.connectForm.baseUrl = provider.default_base_url || provider.base_url || "";
    settingsState.connectForm.showAdvanced = false;
  }

  async function saveProviderConnection() {
    const providerId = settingsState.connectForm.providerId;
    if (!providerId) {
      return;
    }
    settingsState.providersLoading = true;
    settingsState.providersError = "";
    settingsState.providersNotice = "";
    try {
      await requestSettingsJson(`/api/settings/providers/${encodeURIComponent(providerId)}/connect`, {
        method: "PUT",
        body: JSON.stringify({
          name: settingsState.connectForm.name,
          api_key: settingsState.connectForm.apiKey,
          base_url: settingsState.connectForm.baseUrl,
        }),
      });
      setSettingsSuccess("providersNotice", copy.value.notices.providerConnected);
      cancelProviderConnect();
      await refreshProviderState();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerConnectFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  async function disconnectProvider(provider) {
    settingsState.providersLoading = true;
    settingsState.providersError = "";
    settingsState.providersNotice = "";
    try {
      const payload = await requestSettingsJson(`/api/settings/providers/${encodeURIComponent(provider.id)}/disconnect`, {
        method: "POST",
      });
      setSettingsSuccess("providersNotice", copy.value.notices.providerDisconnected(provider.name, payload.restart_required));
      await refreshProviderState();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerDisconnectFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  async function setProviderCredential(provider, credentialId) {
    if (!provider?.id || !credentialId || credentialId === provider.credential_id) {
      return;
    }
    settingsState.providersLoading = true;
    settingsState.providersError = "";
    settingsState.providersNotice = "";
    try {
      const payload = await requestSettingsJson(`/api/settings/providers/${encodeURIComponent(provider.id)}/credential`, {
        method: "POST",
        body: JSON.stringify({ credential_id: credentialId }),
      });
      setSettingsSuccess("providersNotice", copy.value.notices.providerCredentialUpdated(payload.restart_required));
      await refreshProviderState();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerCredentialUpdateFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  async function deleteCredential(provider, credentialId) {
    const providerKey = provider?.provider || provider?.id;
    if (!providerKey || !credentialId) {
      return;
    }
    settingsState.providersLoading = true;
    settingsState.providersError = "";
    settingsState.providersNotice = "";
    try {
      await requestSettingsJson(
        `/api/settings/credentials/${encodeURIComponent(providerKey)}/${encodeURIComponent(credentialId)}`,
        { method: "DELETE" },
      );
      setSettingsSuccess("providersNotice", copy.value.notices.providerCredentialDeleted);
      await refreshProviderState();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerCredentialDeleteFailed;
    } finally {
      settingsState.providersLoading = false;
    }
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
