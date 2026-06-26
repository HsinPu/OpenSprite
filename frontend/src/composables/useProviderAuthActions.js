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
import { providerCatalogKey } from "../settings/providerHelpers";

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
    startAuthLoginById,
    clearProviderAuthPollTimer,
    loadProviderAuthStatusById,
  }));

  function scheduleProviderAuthPollById(providerId) {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    scheduleProviderAuthPoll(config.providerId, settingsState[config.authKey], () => pollProviderAuthLoginById(config.providerId));
  }

  async function loadProviderAuthStatusById(providerId) {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    await runProviderAuthAction(settingsState, copy, config, config.loadFailedNoticeKey, async () => {
      const payload = await requestProviderAuthStatus(requestSettingsJson, config);
      settingsState[config.stateKey] = { ...settingsState[config.stateKey], ...config.normalizeStatus(payload) };
    });
  }

  async function connectOAuthProvider(provider) {
    const config = getProviderAuthConfig(providerAuthConfigs, providerCatalogKey(provider));
    await runProviderMutation(settingsState, copy.value.notices.providerConnectFailed, async () => {
      await requestProviderOAuthConnect(requestSettingsJson, provider, config);
      setSettingsSuccess("providersNotice", copy.value.notices[config.connectedNoticeKey]);
    }, {
      before: () => {
        settingsState[config.noticeKey] = "";
      },
      after: async () => {
        await refreshProviderState();
        await config.startAuthLogin();
      },
    });
  }

  async function startProviderAuthLoginById(providerId) {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
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
      scheduleProviderAuthPollById(config.providerId);
    }, { clearNotice: true, before: config.clearPoll });
  }

  async function pollProviderAuthLoginById(providerId) {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
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
      scheduleProviderAuthPollById(config.providerId);
    } catch (error) {
      setProviderAuthError(settingsState, copy, config, config.loginFailedNoticeKey, error);
      config.clearPoll();
    }
  }

  async function logoutProviderAuthById(providerId) {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
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
    loadProviderAuthStatusById,
    connectOAuthProvider,
    clearProviderAuthPollTimers,
    startProviderAuthLoginById,
    logoutProviderAuthById,
  };
}
