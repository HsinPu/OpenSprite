import { createProviderAuthConfigs, createProviderAuthRuntimeConfigs } from "./providerAuthConfigs";
import { runProviderMutation } from "./providerMutationRunner";
import {
  CODEX_PROVIDER_ID,
  COPILOT_PROVIDER_ID,
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

  const providerAuthConfigs = createProviderAuthConfigs(createProviderAuthRuntimeConfigs({
    copy,
    startAuthLoginById,
    clearProviderAuthPollTimer,
    scheduleProviderAuthPollById,
    loadCodexAuthStatus,
    loadCopilotAuthStatus,
  }));

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
    await runProviderMutation(settingsState, copy.value.notices.providerConnectFailed, async () => {
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
    }, {
      before: () => {
        settingsState[options.noticeKey] = "";
      },
    });
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
