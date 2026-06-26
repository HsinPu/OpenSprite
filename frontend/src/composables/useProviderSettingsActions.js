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

  async function refreshProviderState() { await loadProviderSettings(); await loadModelSettings(); }

  async function loadProviderAuthStatus(config) {
    settingsState[config.loadingKey] = true;
    settingsState[config.errorKey] = "";
    try {
      const payload = await requestSettingsJson(config.endpoint);
      settingsState[config.stateKey] = { ...settingsState[config.stateKey], ...config.normalize(payload) };
    } catch (error) {
      settingsState[config.errorKey] = error?.message || copy.value.notices[config.loadFailedNoticeKey];
    } finally {
      settingsState[config.loadingKey] = false;
    }
  }

  const providerAuthStatusConfigs = {
    "openai-codex": {
      endpoint: "/api/settings/auth/openai-codex",
      loadingKey: "codexAuthLoading",
      errorKey: "codexAuthError",
      stateKey: "codexAuth",
      loadFailedNoticeKey: "codexAuthLoadFailed",
      normalize: (payload) => ({
        configured: Boolean(payload.configured),
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
        path: payload.path || "",
      }),
    },
    copilot: {
      endpoint: "/api/settings/auth/copilot",
      loadingKey: "copilotAuthLoading",
      errorKey: "copilotAuthError",
      stateKey: "copilotAuth",
      loadFailedNoticeKey: "copilotAuthLoadFailed",
      normalize: (payload) => ({
        configured: Boolean(payload.configured),
        path: payload.path || "",
      }),
    },
  };

  function providerAuthStatusConfig(providerId) {
    return providerAuthStatusConfigs[providerId] || providerAuthStatusConfigs["openai-codex"];
  }

  async function loadProviderAuthStatusById(providerId) {
    return loadProviderAuthStatus(providerAuthStatusConfig(providerId));
  }

  async function loadCodexAuthStatus() {
    return loadProviderAuthStatusById("openai-codex");
  }

  async function loadCopilotAuthStatus() {
    return loadProviderAuthStatusById("copilot");
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

  async function connectOAuthBackedProvider(provider, options) {
    const providerId = provider?.id || options.providerId;
    settingsState.providersLoading = true;
    settingsState.providersError = "";
    settingsState.providersNotice = "";
    settingsState[options.authNoticeKey] = "";
    try {
      await requestSettingsJson(`/api/settings/providers/${encodeURIComponent(providerId)}/connect`, {
        method: "PUT",
        body: JSON.stringify({
          name: provider?.name || options.providerName,
          base_url: provider?.default_base_url || "",
        }),
      });
      setSettingsSuccess("providersNotice", options.connectedNotice);
      await refreshProviderState();
      await options.startAuthLogin();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerConnectFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  const oauthProviderConfigs = {
    "openai-codex": {
      providerId: "openai-codex",
      providerName: "OpenAI Codex",
      authNoticeKey: "codexAuthNotice",
      connectedNotice: () => copy.value.notices.codexProviderConnected,
      startAuthLogin: startCodexAuthLogin,
    },
    copilot: {
      providerId: "copilot",
      providerName: "GitHub Copilot",
      authNoticeKey: "copilotAuthNotice",
      connectedNotice: () => copy.value.notices.copilotProviderConnected,
      startAuthLogin: startCopilotAuthLogin,
    },
  };

  function oauthProviderConfig(providerId) {
    return oauthProviderConfigs[providerId] || oauthProviderConfigs["openai-codex"];
  }

  async function connectOAuthProviderById(provider, providerId) {
    const config = oauthProviderConfig(providerId);
    return connectOAuthBackedProvider(provider, {
      ...config,
      connectedNotice: config.connectedNotice(),
    });
  }

  async function connectCodexProvider(provider) {
    return connectOAuthProviderById(provider, "openai-codex");
  }

  async function connectCopilotProvider(provider) {
    return connectOAuthProviderById(provider, "copilot");
  }

  async function connectOAuthProvider(provider) {
    await connectOAuthProviderById(provider, provider?.id === "copilot" ? "copilot" : "openai-codex");
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
