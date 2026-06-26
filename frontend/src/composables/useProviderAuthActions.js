import { runProviderAuthAction, setProviderAuthError } from "./providerAuthActionRunner";
import {
  createProviderAuthConfigs,
  createProviderAuthRuntimeConfigs,
  getProviderAuthConfig,
} from "./providerAuthConfigs";
import { createProviderAuthPollTimers } from "./providerAuthPollTimers";
import {
  requestProviderAuthLogin,
  requestProviderAuthLogout,
  requestProviderAuthPoll,
  requestProviderAuthStatus,
  requestProviderOAuthConnect,
} from "./providerAuthRequests";
import { runProviderMutation } from "./providerMutationRunner";
import {
  CODEX_PROVIDER_ID,
  COPILOT_PROVIDER_ID,
} from "../settings/providerConstants";

export function useProviderAuthActions({
  settingsState,
  requestSettingsJson,
  copy,
  setSettingsSuccess,
  loadModelSettings,
  refreshProviderState,
}) {
  const {
    clearProviderAuthPollTimer,
    scheduleProviderAuthPoll,
    clearProviderAuthPollTimers: clearProviderAuthPollTimersById,
  } = createProviderAuthPollTimers();

  const providerAuthConfigs = createProviderAuthConfigs(createProviderAuthRuntimeConfigs({
    copy,
    startAuthLoginById,
    clearProviderAuthPollTimer,
    scheduleProviderAuthPollById,
    loadCodexAuthStatus,
    loadCopilotAuthStatus,
  }));

  function scheduleProviderAuthPollById(providerId) {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    scheduleProviderAuthPoll(config.providerId, settingsState[config.authKey], () => pollProviderAuthLoginById(config.providerId));
  }

  async function loadProviderAuthStatus(config) {
    await runProviderAuthAction(settingsState, copy, config, config.loadFailedNoticeKey, async () => {
      const payload = await requestProviderAuthStatus(requestSettingsJson, config);
      settingsState[config.stateKey] = { ...settingsState[config.stateKey], ...config.normalizeStatus(payload) };
    });
  }

  async function loadProviderAuthStatusById(providerId) {
    return loadProviderAuthStatus(getProviderAuthConfig(providerAuthConfigs, providerId));
  }

  async function loadCodexAuthStatus() {
    return loadProviderAuthStatusById(CODEX_PROVIDER_ID);
  }

  async function loadCopilotAuthStatus() {
    return loadProviderAuthStatusById(COPILOT_PROVIDER_ID);
  }

  async function connectOAuthBackedProvider(provider, options) {
    await runProviderMutation(settingsState, copy.value.notices.providerConnectFailed, async () => {
      await requestProviderOAuthConnect(requestSettingsJson, provider, options);
      setSettingsSuccess("providersNotice", options.connectedNotice());
    }, {
      before: () => {
        settingsState[options.noticeKey] = "";
      },
      after: async () => {
        await refreshProviderState();
        await options.startAuthLogin();
      },
    });
  }

  async function connectOAuthProviderById(provider, providerId) {
    return connectOAuthBackedProvider(provider, getProviderAuthConfig(providerAuthConfigs, providerId));
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
    await runProviderAuthAction(settingsState, copy, config, config.loginFailedNoticeKey, async () => {
      const payload = await requestProviderAuthLogin(requestSettingsJson, config);
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

  async function logoutCodexAuth() {
    return logoutProviderAuthById(CODEX_PROVIDER_ID);
  }

  async function startCopilotAuthLogin() {
    return startProviderAuthLoginById(COPILOT_PROVIDER_ID);
  }

  async function logoutCopilotAuth() {
    return logoutProviderAuthById(COPILOT_PROVIDER_ID);
  }

  async function startProviderAuthLoginById(providerId) {
    return startProviderAuthLogin(getProviderAuthConfig(providerAuthConfigs, providerId));
  }

  async function pollProviderAuthLoginById(providerId) {
    return pollProviderAuthLogin(getProviderAuthConfig(providerAuthConfigs, providerId));
  }

  async function logoutProviderAuthById(providerId) {
    return logoutProviderAuth(getProviderAuthConfig(providerAuthConfigs, providerId));
  }

  async function pollProviderAuthLogin(config) {
    const pendingAuth = settingsState[config.authKey] || {};
    if (!config.hasPendingPoll(pendingAuth)) return;
    try {
      const payload = await requestProviderAuthPoll(requestSettingsJson, config, pendingAuth);
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
      setProviderAuthError(settingsState, copy, config, config.loginFailedNoticeKey, error);
      config.clearPoll();
    }
  }

  async function logoutProviderAuth(config) {
    await runProviderAuthAction(settingsState, copy, config, config.logoutFailedNoticeKey, async () => {
      await requestProviderAuthLogout(requestSettingsJson, config);
      settingsState[config.authKey] = config.resetLogout(settingsState[config.authKey]);
      setSettingsSuccess(config.noticeKey, copy.value.notices[config.loggedOutNoticeKey]);
    }, { clearNotice: true, before: config.clearPoll, after: config.loadStatus });
  }

  function clearProviderAuthPollTimers() {
    clearProviderAuthPollTimersById(Object.keys(providerAuthConfigs));
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
