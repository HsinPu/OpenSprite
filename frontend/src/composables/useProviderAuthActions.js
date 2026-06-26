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

  function providerAuthRuntimeConfig(providerId, providerName, connectedNoticeKey, loadStatus) {
    return {
      providerName,
      connectedNotice: () => copy.value.notices[connectedNoticeKey],
      startAuthLogin: () => startProviderAuthLoginById(providerId),
      clearPoll: () => clearProviderAuthPollTimer(providerId),
      schedulePoll: () => scheduleProviderAuthPollById(providerId),
      loadStatus,
    };
  }

  function normalizeDeviceAuthLogin(payload, deviceKey, payloadDeviceKey, extra = {}) {
    return {
      ...extra,
      verificationUri: payload.verification_uri || "",
      userCode: payload.user_code || "",
      [deviceKey]: payload[payloadDeviceKey] || "",
      pollIntervalSeconds: coerceNonNegativeInteger(payload.interval) || 5,
    };
  }

  const providerAuthConfigs = {
    [CODEX_PROVIDER_ID]: {
      ...providerAuthRequestConfig(CODEX_PROVIDER_ID, CODEX_AUTH_STATE_KEYS),
      ...providerAuthRuntimeConfig(CODEX_PROVIDER_ID, CODEX_PROVIDER_NAME, "codexProviderConnected", loadCodexAuthStatus),
      hasPendingPoll: (auth) => Boolean(auth.deviceAuthId && auth.userCode),
      buildPollBody: (auth) => ({ device_auth_id: auth.deviceAuthId, user_code: auth.userCode }),
      normalizeStatus: (payload) => ({
        configured: Boolean(payload.configured),
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
        path: payload.path || "",
      }),
      normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, "deviceAuthId", "device_auth_id", { command: "" }),
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
      ...providerAuthRuntimeConfig(COPILOT_PROVIDER_ID, COPILOT_PROVIDER_NAME, "copilotProviderConnected", loadCopilotAuthStatus),
      hasPendingPoll: (auth) => Boolean(auth.deviceCode),
      buildPollBody: (auth) => ({ device_code: auth.deviceCode }),
      normalizeStatus: (payload) => ({
        configured: Boolean(payload.configured),
        path: payload.path || "",
      }),
      normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, "deviceCode", "device_code"),
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

  async function runProviderAuthAction(config, fallbackNoticeKey, action, options = {}) {
    options.before?.();
    settingsState[config.loadingKey] = true;
    settingsState[config.errorKey] = "";
    if (options.clearNotice) {
      settingsState[config.noticeKey] = "";
    }
    try {
      await action();
    } catch (error) {
      settingsState[config.errorKey] = error?.message || copy.value.notices[fallbackNoticeKey];
    } finally {
      settingsState[config.loadingKey] = false;
    }
  }

  async function loadProviderAuthStatus(config) {
    await runProviderAuthAction(config, config.loadFailedNoticeKey, async () => {
      const payload = await requestSettingsJson(config.endpoint);
      settingsState[config.stateKey] = { ...settingsState[config.stateKey], ...config.normalizeStatus(payload) };
    });
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
    await runProviderAuthAction(config, config.loginFailedNoticeKey, async () => {
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
    }, { clearNotice: true, before: config.clearPoll });
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
    await runProviderAuthAction(config, config.logoutFailedNoticeKey, async () => {
      await requestSettingsJson(config.logoutEndpoint, { method: "POST" });
      settingsState[config.authKey] = config.resetLogout(settingsState[config.authKey]);
      setSettingsSuccess(config.noticeKey, copy.value.notices[config.loggedOutNoticeKey]);
      await config.loadStatus();
    }, { clearNotice: true, before: config.clearPoll });
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
