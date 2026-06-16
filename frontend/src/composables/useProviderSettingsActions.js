export function useProviderSettingsActions({
  settingsState,
  requestSettingsJson,
  copy,
  setSettingsSuccess,
  cancelChannelConnect,
  cancelProviderConnect,
  loadModelSettings,
  startCodexAuthLogin,
  startCopilotAuthLogin,
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

  async function loadCodexAuthStatus() {
    settingsState.codexAuthLoading = true;
    settingsState.codexAuthError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/auth/openai-codex");
      settingsState.codexAuth = {
        ...settingsState.codexAuth,
        configured: Boolean(payload.configured),
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
        path: payload.path || "",
      };
    } catch (error) {
      settingsState.codexAuthError = error?.message || copy.value.notices.codexAuthLoadFailed;
    } finally {
      settingsState.codexAuthLoading = false;
    }
  }

  async function loadCopilotAuthStatus() {
    settingsState.copilotAuthLoading = true;
    settingsState.copilotAuthError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/auth/copilot");
      settingsState.copilotAuth = {
        ...settingsState.copilotAuth,
        configured: Boolean(payload.configured),
        path: payload.path || "",
      };
    } catch (error) {
      settingsState.copilotAuthError = error?.message || copy.value.notices.copilotAuthLoadFailed;
    } finally {
      settingsState.copilotAuthLoading = false;
    }
  }

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
      await loadProviderSettings();
      await loadModelSettings();
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
      await loadProviderSettings();
      await loadModelSettings();
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
      await loadProviderSettings();
      await loadModelSettings();
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
      await loadProviderSettings();
      await loadModelSettings();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerCredentialDeleteFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  async function connectCodexProvider(provider) {
    const providerId = provider?.id || "openai-codex";
    settingsState.providersLoading = true;
    settingsState.providersError = "";
    settingsState.providersNotice = "";
    settingsState.codexAuthNotice = "";
    try {
      await requestSettingsJson(`/api/settings/providers/${encodeURIComponent(providerId)}/connect`, {
        method: "PUT",
        body: JSON.stringify({
          name: provider?.name || "OpenAI Codex",
          base_url: provider?.default_base_url || "",
        }),
      });
      setSettingsSuccess("providersNotice", copy.value.notices.codexProviderConnected);
      await loadProviderSettings();
      await loadModelSettings();
      await startCodexAuthLogin();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerConnectFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  async function connectCopilotProvider(provider) {
    const providerId = provider?.id || "copilot";
    settingsState.providersLoading = true;
    settingsState.providersError = "";
    settingsState.providersNotice = "";
    settingsState.copilotAuthNotice = "";
    try {
      await requestSettingsJson(`/api/settings/providers/${encodeURIComponent(providerId)}/connect`, {
        method: "PUT",
        body: JSON.stringify({ name: provider?.name || "GitHub Copilot", base_url: provider?.default_base_url || "" }),
      });
      setSettingsSuccess("providersNotice", copy.value.notices.copilotProviderConnected);
      await loadProviderSettings();
      await loadModelSettings();
      await startCopilotAuthLogin();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerConnectFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  async function connectOAuthProvider(provider) {
    if (provider?.id === "copilot") {
      await connectCopilotProvider(provider);
      return;
    }
    await connectCodexProvider(provider);
  }

  return {
    loadProviderSettings,
    loadCodexAuthStatus,
    loadCopilotAuthStatus,
    beginProviderConnect,
    saveProviderConnection,
    disconnectProvider,
    setProviderCredential,
    deleteCredential,
    connectCodexProvider,
    connectOAuthProvider,
    connectCopilotProvider,
  };
}
