import { coerceNonNegativeInteger } from "./chatClientCoercion";
import {
  CODEX_AUTH_STATE_KEYS,
  CODEX_PROVIDER_ID,
  CODEX_PROVIDER_NAME,
  COPILOT_AUTH_STATE_KEYS,
  COPILOT_PROVIDER_ID,
  COPILOT_PROVIDER_NAME,
  providerAuthRequestConfig,
  providerSettingsEndpoint,
} from "../settings/providerConstants";

export function useProviderAuthActions({
  settingsState,
  requestSettingsJson,
  copy,
  setSettingsSuccess,
  loadModelSettings,
  refreshProviderState,
}) {
  const providerAuthPollTimers = new Map();

  function clearProviderAuthPollTimer(providerId) {
    const timer = providerAuthPollTimers.get(providerId);
    if (timer) {
      clearTimeout(timer);
      providerAuthPollTimers.delete(providerId);
    }
  }

  function scheduleProviderAuthPoll(providerId, auth, poll) {
    clearProviderAuthPollTimer(providerId);
    const delayMs = Math.max(3, auth.pollIntervalSeconds || 5) * 1000;
    providerAuthPollTimers.set(providerId, window.setTimeout(() => {
      void poll();
    }, delayMs));
  }

  const providerAuthConfigs = {
    [CODEX_PROVIDER_ID]: {
      ...providerAuthRequestConfig(CODEX_PROVIDER_ID, CODEX_AUTH_STATE_KEYS),
      providerName: CODEX_PROVIDER_NAME,
      connectedNotice: () => copy.value.notices.codexProviderConnected,
      startAuthLogin: () => startProviderAuthLoginById(CODEX_PROVIDER_ID),
      clearPoll: () => clearProviderAuthPollTimer(CODEX_PROVIDER_ID),
      schedulePoll: () => scheduleProviderAuthPollById(CODEX_PROVIDER_ID),
      hasPendingPoll: (auth) => Boolean(auth.deviceAuthId && auth.userCode),
      buildPollBody: (auth) => ({ device_auth_id: auth.deviceAuthId, user_code: auth.userCode }),
      loadStatus: loadCodexAuthStatus,
      normalizeStatus: (payload) => ({
        configured: Boolean(payload.configured),
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
        path: payload.path || "",
      }),
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
      providerName: COPILOT_PROVIDER_NAME,
      connectedNotice: () => copy.value.notices.copilotProviderConnected,
      startAuthLogin: () => startProviderAuthLoginById(COPILOT_PROVIDER_ID),
      clearPoll: () => clearProviderAuthPollTimer(COPILOT_PROVIDER_ID),
      schedulePoll: () => scheduleProviderAuthPollById(COPILOT_PROVIDER_ID),
      hasPendingPoll: (auth) => Boolean(auth.deviceCode),
      buildPollBody: (auth) => ({ device_code: auth.deviceCode }),
      loadStatus: loadCopilotAuthStatus,
      normalizeStatus: (payload) => ({
        configured: Boolean(payload.configured),
        path: payload.path || "",
      }),
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

  function resolveProviderAuthId(providerId) {
    return providerAuthConfigs[providerId] ? providerId : CODEX_PROVIDER_ID;
  }

  function providerAuthConfig(providerId) {
    return providerAuthConfigs[resolveProviderAuthId(providerId)];
  }

  function scheduleProviderAuthPollById(providerId) {
    const resolvedProviderId = resolveProviderAuthId(providerId);
    const config = providerAuthConfig(resolvedProviderId);
    scheduleProviderAuthPoll(resolvedProviderId, settingsState[config.authKey], () => pollProviderAuthLoginById(resolvedProviderId));
  }

  async function loadProviderAuthStatus(config) {
    settingsState[config.loadingKey] = true;
    settingsState[config.errorKey] = "";
    try {
      const payload = await requestSettingsJson(config.endpoint);
      settingsState[config.stateKey] = { ...settingsState[config.stateKey], ...config.normalizeStatus(payload) };
    } catch (error) {
      settingsState[config.errorKey] = error?.message || copy.value.notices[config.loadFailedNoticeKey];
    } finally {
      settingsState[config.loadingKey] = false;
    }
  }

  async function loadProviderAuthStatusById(providerId) {
    return loadProviderAuthStatus(providerAuthConfig(providerId));
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
    settingsState[options.noticeKey] = "";
    try {
      await requestSettingsJson(providerSettingsEndpoint(providerId, "connect"), {
        method: "PUT",
        body: JSON.stringify({
          name: provider?.name || options.providerName,
          base_url: provider?.default_base_url || "",
        }),
      });
      setSettingsSuccess("providersNotice", options.connectedNotice());
      await refreshProviderState();
      await options.startAuthLogin();
    } catch (error) {
      settingsState.providersError = error?.message || copy.value.notices.providerConnectFailed;
    } finally {
      settingsState.providersLoading = false;
    }
  }

  async function connectOAuthProviderById(provider, providerId) {
    return connectOAuthBackedProvider(provider, providerAuthConfig(providerId));
  }

  async function connectCodexProvider(provider) {
    return connectOAuthProviderById(provider, CODEX_PROVIDER_ID);
  }

  async function connectCopilotProvider(provider) {
    return connectOAuthProviderById(provider, COPILOT_PROVIDER_ID);
  }

  async function connectOAuthProvider(provider) {
    await connectOAuthProviderById(provider, provider?.id);
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
    return startProviderAuthLoginById(CODEX_PROVIDER_ID);
  }

  async function pollCodexAuthLogin() {
    return pollProviderAuthLoginById(CODEX_PROVIDER_ID);
  }

  async function logoutCodexAuth() {
    return logoutProviderAuthById(CODEX_PROVIDER_ID);
  }

  async function startCopilotAuthLogin() {
    return startProviderAuthLoginById(COPILOT_PROVIDER_ID);
  }

  async function pollCopilotAuthLogin() {
    return pollProviderAuthLoginById(COPILOT_PROVIDER_ID);
  }

  async function logoutCopilotAuth() {
    return logoutProviderAuthById(COPILOT_PROVIDER_ID);
  }

  async function startProviderAuthLoginById(providerId) {
    return startProviderAuthLogin(providerAuthConfig(providerId));
  }

  async function pollProviderAuthLoginById(providerId) {
    return pollProviderAuthLogin(providerAuthConfig(providerId));
  }

  async function logoutProviderAuthById(providerId) {
    return logoutProviderAuth(providerAuthConfig(providerId));
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
    for (const providerId of Object.keys(providerAuthConfigs)) {
      clearProviderAuthPollTimer(providerId);
    }
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
