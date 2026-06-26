import {
  CODEX_AUTH_STATE_KEYS,
  CODEX_PROVIDER_ID,
  CODEX_PROVIDER_NAME,
  COPILOT_AUTH_STATE_KEYS,
  COPILOT_PROVIDER_ID,
  COPILOT_PROVIDER_NAME,
  providerAuthEndpoint,
} from "../settings/providerConstants";

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
    [CODEX_PROVIDER_ID]: {
      endpoint: providerAuthEndpoint(CODEX_PROVIDER_ID),
      ...CODEX_AUTH_STATE_KEYS,
      normalize: (payload) => ({
        configured: Boolean(payload.configured),
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
        path: payload.path || "",
      }),
    },
    [COPILOT_PROVIDER_ID]: {
      endpoint: providerAuthEndpoint(COPILOT_PROVIDER_ID),
      ...COPILOT_AUTH_STATE_KEYS,
      normalize: (payload) => ({
        configured: Boolean(payload.configured),
        path: payload.path || "",
      }),
    },
  };

  function providerAuthStatusConfig(providerId) {
    return providerAuthStatusConfigs[providerId] || providerAuthStatusConfigs[CODEX_PROVIDER_ID];
  }

  async function loadProviderAuthStatusById(providerId) {
    return loadProviderAuthStatus(providerAuthStatusConfig(providerId));
  }

  async function loadCodexAuthStatus() {
    return loadProviderAuthStatusById(CODEX_PROVIDER_ID);
  }

  async function loadCopilotAuthStatus() {
    return loadProviderAuthStatusById(COPILOT_PROVIDER_ID);
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
    [CODEX_PROVIDER_ID]: {
      providerId: CODEX_PROVIDER_ID,
      providerName: CODEX_PROVIDER_NAME,
      authNoticeKey: CODEX_AUTH_STATE_KEYS.noticeKey,
      connectedNotice: () => copy.value.notices.codexProviderConnected,
      startAuthLogin: startCodexAuthLogin,
    },
    [COPILOT_PROVIDER_ID]: {
      providerId: COPILOT_PROVIDER_ID,
      providerName: COPILOT_PROVIDER_NAME,
      authNoticeKey: COPILOT_AUTH_STATE_KEYS.noticeKey,
      connectedNotice: () => copy.value.notices.copilotProviderConnected,
      startAuthLogin: startCopilotAuthLogin,
    },
  };

  function oauthProviderConfig(providerId) {
    return oauthProviderConfigs[providerId] || oauthProviderConfigs[CODEX_PROVIDER_ID];
  }

  async function connectOAuthProviderById(provider, providerId) {
    const config = oauthProviderConfig(providerId);
    return connectOAuthBackedProvider(provider, {
      ...config,
      connectedNotice: config.connectedNotice(),
    });
  }

  async function connectCodexProvider(provider) {
    return connectOAuthProviderById(provider, CODEX_PROVIDER_ID);
  }

  async function connectCopilotProvider(provider) {
    return connectOAuthProviderById(provider, COPILOT_PROVIDER_ID);
  }

  async function connectOAuthProvider(provider) {
    await connectOAuthProviderById(provider, provider?.id === COPILOT_PROVIDER_ID ? COPILOT_PROVIDER_ID : CODEX_PROVIDER_ID);
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
