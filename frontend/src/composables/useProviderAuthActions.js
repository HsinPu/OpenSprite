import { coerceNonNegativeInteger } from "./chatClientCoercion";
import {
  CODEX_AUTH_STATE_KEYS,
  CODEX_PROVIDER_ID,
  CODEX_PROVIDER_NAME,
  COPILOT_AUTH_STATE_KEYS,
  COPILOT_PROVIDER_ID,
  COPILOT_PROVIDER_NAME,
  providerAuthRequestConfig,
} from "../settings/providerConstants";

export function useProviderAuthActions({
  settingsState,
  requestSettingsJson,
  copy,
  setSettingsSuccess,
  loadModelSettings,
  refreshProviderState,
}) {
  const providerAuthPollTimers = {
    [CODEX_PROVIDER_ID]: null,
    [COPILOT_PROVIDER_ID]: null,
  };

  function clearProviderAuthPollTimer(providerId) {
    if (providerAuthPollTimers[providerId]) {
      clearTimeout(providerAuthPollTimers[providerId]);
      providerAuthPollTimers[providerId] = null;
    }
  }

  function scheduleProviderAuthPoll(providerId, auth, poll) {
    clearProviderAuthPollTimer(providerId);
    const delayMs = Math.max(3, auth.pollIntervalSeconds || 5) * 1000;
    providerAuthPollTimers[providerId] = window.setTimeout(() => {
      void poll();
    }, delayMs);
  }

  function clearCodexAuthPollTimer() {
    clearProviderAuthPollTimer(CODEX_PROVIDER_ID);
  }

  function scheduleCodexAuthPoll() {
    scheduleProviderAuthPoll(CODEX_PROVIDER_ID, settingsState[CODEX_AUTH_STATE_KEYS.authKey], pollCodexAuthLogin);
  }

  function clearCopilotAuthPollTimer() {
    clearProviderAuthPollTimer(COPILOT_PROVIDER_ID);
  }

  function scheduleCopilotAuthPoll() {
    scheduleProviderAuthPoll(COPILOT_PROVIDER_ID, settingsState[COPILOT_AUTH_STATE_KEYS.authKey], pollCopilotAuthLogin);
  }

  const providerAuthFlowConfigs = {
    [CODEX_PROVIDER_ID]: {
      ...providerAuthRequestConfig(CODEX_PROVIDER_ID, CODEX_AUTH_STATE_KEYS),
      clearPoll: clearCodexAuthPollTimer,
      schedulePoll: scheduleCodexAuthPoll,
      hasPendingPoll: (auth) => Boolean(auth.deviceAuthId && auth.userCode),
      buildPollBody: (auth) => ({ device_auth_id: auth.deviceAuthId, user_code: auth.userCode }),
      loadStatus: loadCodexAuthStatus,
      normalizeLogin: (payload) => ({
        command: "",
        verificationUri: payload.verification_uri || "",
        userCode: payload.user_code || "",
        deviceAuthId: payload.device_auth_id || "",
        pollIntervalSeconds: coerceNonNegativeInteger(payload.interval) || 5,
      }),
      normalizeAuthorized: (auth, currentAuth) => ({
        configured: Boolean(auth.configured),
        expired: Boolean(auth.expired),
        expires_at: auth.expires_at || null,
        account_id: auth.account_id || "",
        path: auth.path || currentAuth.path,
        verificationUri: "",
        userCode: "",
        deviceAuthId: "",
      }),
      resetLogout: (auth) => ({
        ...auth,
        configured: false,
        expired: false,
        expires_at: null,
        account_id: "",
        command: "",
        verificationUri: "",
        userCode: "",
        deviceAuthId: "",
      }),
    },
    [COPILOT_PROVIDER_ID]: {
      ...providerAuthRequestConfig(COPILOT_PROVIDER_ID, COPILOT_AUTH_STATE_KEYS),
      clearPoll: clearCopilotAuthPollTimer,
      schedulePoll: scheduleCopilotAuthPoll,
      hasPendingPoll: (auth) => Boolean(auth.deviceCode),
      buildPollBody: (auth) => ({ device_code: auth.deviceCode }),
      loadStatus: loadCopilotAuthStatus,
      normalizeLogin: (payload) => ({
        verificationUri: payload.verification_uri || "",
        userCode: payload.user_code || "",
        deviceCode: payload.device_code || "",
        pollIntervalSeconds: coerceNonNegativeInteger(payload.interval) || 5,
      }),
      normalizeAuthorized: (auth, currentAuth) => ({
        configured: Boolean(auth.configured),
        path: auth.path || currentAuth.path,
        verificationUri: "",
        userCode: "",
        deviceCode: "",
      }),
      resetLogout: (auth) => ({ ...auth, configured: false, path: "", verificationUri: "", userCode: "", deviceCode: "" }),
    },
  };

  const providerAuthStatusConfigs = {
    [CODEX_PROVIDER_ID]: {
      ...providerAuthRequestConfig(CODEX_PROVIDER_ID, CODEX_AUTH_STATE_KEYS),
      normalize: (payload) => ({
        configured: Boolean(payload.configured),
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
        path: payload.path || "",
      }),
    },
    [COPILOT_PROVIDER_ID]: {
      ...providerAuthRequestConfig(COPILOT_PROVIDER_ID, COPILOT_AUTH_STATE_KEYS),
      normalize: (payload) => ({
        configured: Boolean(payload.configured),
        path: payload.path || "",
      }),
    },
  };

  function providerAuthStatusConfig(providerId) {
    return providerAuthStatusConfigs[providerId] || providerAuthStatusConfigs[CODEX_PROVIDER_ID];
  }

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

  async function loadProviderAuthStatusById(providerId) {
    return loadProviderAuthStatus(providerAuthStatusConfig(providerId));
  }

  async function loadCodexAuthStatus() {
    return loadProviderAuthStatusById(CODEX_PROVIDER_ID);
  }

  async function loadCopilotAuthStatus() {
    return loadProviderAuthStatusById(COPILOT_PROVIDER_ID);
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

  async function startProviderAuthLogin(config) {
    config.clearPoll();
    settingsState[config.loadingKey] = true;
    settingsState[config.errorKey] = "";
    settingsState[config.noticeKey] = "";
    try {
      const payload = await requestSettingsJson(config.loginEndpoint, { method: "POST" });
      settingsState[config.authKey] = {
        ...settingsState[config.authKey],
        ...config.normalizeLogin(payload),
      };
      if (settingsState[config.authKey].verificationUri) {
        window.open(settingsState[config.authKey].verificationUri, "_blank", "noopener,noreferrer");
      }
      setSettingsSuccess(config.noticeKey, copy.value.notices[config.loginReadyNoticeKey]);
      config.schedulePoll();
    } catch (error) {
      settingsState[config.errorKey] = error?.message || copy.value.notices[config.loginFailedNoticeKey];
    } finally {
      settingsState[config.loadingKey] = false;
    }
  }

  async function startCodexAuthLogin() {
    return startProviderAuthLogin(providerAuthFlowConfigs[CODEX_PROVIDER_ID]);
  }

  async function pollCodexAuthLogin() {
    return pollProviderAuthLogin(providerAuthFlowConfigs[CODEX_PROVIDER_ID]);
  }

  async function logoutCodexAuth() {
    return logoutProviderAuth(providerAuthFlowConfigs[CODEX_PROVIDER_ID]);
  }

  async function startCopilotAuthLogin() {
    return startProviderAuthLogin(providerAuthFlowConfigs[COPILOT_PROVIDER_ID]);
  }

  async function pollCopilotAuthLogin() {
    return pollProviderAuthLogin(providerAuthFlowConfigs[COPILOT_PROVIDER_ID]);
  }

  async function logoutCopilotAuth() {
    return logoutProviderAuth(providerAuthFlowConfigs[COPILOT_PROVIDER_ID]);
  }

  async function pollProviderAuthLogin(config) {
    const pendingAuth = settingsState[config.authKey] || {};
    if (!config.hasPendingPoll(pendingAuth)) return;
    try {
      const payload = await requestSettingsJson(config.pollEndpoint, {
        method: "POST",
        body: JSON.stringify(config.buildPollBody(pendingAuth)),
      });
      if (payload.status === "authorized") {
        const auth = payload.auth || {};
        const currentAuth = settingsState[config.authKey] || {};
        settingsState[config.authKey] = {
          ...currentAuth,
          ...config.normalizeAuthorized(auth, currentAuth),
        };
        setSettingsSuccess(config.noticeKey, copy.value.notices[config.loginCompleteNoticeKey]);
        await loadModelSettings();
        return;
      }
      config.schedulePoll();
    } catch (error) {
      settingsState[config.errorKey] = error?.message || copy.value.notices[config.loginFailedNoticeKey];
      config.clearPoll();
    }
  }

  async function logoutProviderAuth(config) {
    config.clearPoll();
    settingsState[config.loadingKey] = true;
    settingsState[config.errorKey] = "";
    settingsState[config.noticeKey] = "";
    try {
      await requestSettingsJson(config.logoutEndpoint, { method: "POST" });
      settingsState[config.authKey] = config.resetLogout(settingsState[config.authKey]);
      setSettingsSuccess(config.noticeKey, copy.value.notices[config.loggedOutNoticeKey]);
      await config.loadStatus();
    } catch (error) {
      settingsState[config.errorKey] = error?.message || copy.value.notices[config.logoutFailedNoticeKey];
    } finally {
      settingsState[config.loadingKey] = false;
    }
  }

  function clearProviderAuthPollTimers() {
    clearCodexAuthPollTimer();
    clearCopilotAuthPollTimer();
  }

  return {
    loadCodexAuthStatus,
    loadCopilotAuthStatus,
    connectCodexProvider,
    connectOAuthProvider,
    connectCopilotProvider,
    clearProviderAuthPollTimers,
    startCodexAuthLogin,
    logoutCodexAuth,
    startCopilotAuthLogin,
    logoutCopilotAuth,
  };
}
