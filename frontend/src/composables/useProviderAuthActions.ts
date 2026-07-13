import {
  runProviderAuthAction,
  setProviderAuthError,
  type ProviderAuthActionState,
} from "./providerAuthActionRunner";
import {
  createProviderAuthConfigs,
  getProviderAuthConfig,
  type ProviderAuthConfig,
} from "./providerAuthConfigs";
import { createProviderAuthPollTimers } from "./providerAuthPollTimers";
import {
  requestProviderAuthLogin,
  requestProviderAuthLogout,
  requestProviderAuthPoll,
  requestProviderAuthStatus,
  requestProviderOAuthConnect,
} from "./providerAuthRequests";
import type { ProviderAuthStatePayload } from "./providerAuthState";
import { runProviderMutation } from "./providerMutationRunner";
import type { ProviderPayload } from "./providerConnectForm";
import { providerCatalogKey } from "../settings/providerHelpers";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type ProviderMutationState = {
  providersLoading: boolean;
  providersError: string;
  providersNotice: string;
};
type ProviderAuthNoticeValue = string;
type ProviderAuthActionsState = ProviderMutationState & ProviderAuthActionState;
type ProviderAuthActionsCopy = {
  value: {
    notices: Record<string, string>;
  };
};
type ProviderAuthActionsContext = {
  settingsState: ProviderAuthActionsState;
  requestSettingsJson: RequestSettingsJson;
  copy: ProviderAuthActionsCopy;
  setSettingsSuccess: (key: string, message: string) => void;
  loadModelSettings: () => Promise<void>;
  refreshProviderState: () => Promise<void>;
};

function authStateForConfig(settingsState: ProviderAuthActionsState, config: ProviderAuthConfig): ProviderAuthStatePayload {
  return settingsState[config.stateKey];
}

function setAuthStateForConfig(settingsState: ProviderAuthActionsState, config: ProviderAuthConfig, auth: ProviderAuthStatePayload): void {
  settingsState[config.stateKey] = auth;
}

function setAuthNoticeForConfig(settingsState: ProviderAuthActionsState, config: ProviderAuthConfig, notice: ProviderAuthNoticeValue): void {
  settingsState[config.noticeKey] = notice;
}

function authNotice(copy: ProviderAuthActionsCopy, key: string): string {
  return copy.value.notices[key] || "";
}

export function useProviderAuthActions({
  settingsState,
  requestSettingsJson,
  copy,
  setSettingsSuccess,
  loadModelSettings,
  refreshProviderState,
}: ProviderAuthActionsContext) {
  const {
    clearProviderAuthPollTimer,
    scheduleProviderAuthPoll,
    clearProviderAuthPollTimers: clearProviderAuthPollTimersById,
  } = createProviderAuthPollTimers();

  const providerAuthConfigs = createProviderAuthConfigs();

  function scheduleProviderAuthPollById(providerId: string): void {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    scheduleProviderAuthPoll(config.providerId, authStateForConfig(settingsState, config), () => pollProviderAuthLoginById(config.providerId));
  }

  async function loadProviderAuthStatusById(providerId: string): Promise<void> {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    await runProviderAuthAction(settingsState, copy, config, config.loadFailedNoticeKey, async () => {
      const payload = await requestProviderAuthStatus(requestSettingsJson, config);
      setAuthStateForConfig(settingsState, config, { ...authStateForConfig(settingsState, config), ...config.normalizeStatus(payload) });
    });
  }

  async function connectOAuthProvider(provider: ProviderPayload): Promise<void> {
    const config = getProviderAuthConfig(providerAuthConfigs, providerCatalogKey(provider));
    await runProviderMutation(settingsState, copy.value.notices.providerConnectFailed, async () => {
      await requestProviderOAuthConnect(requestSettingsJson, provider, config);
      setSettingsSuccess("providersNotice", authNotice(copy, config.connectedNoticeKey));
    }, {
      before: () => {
        setAuthNoticeForConfig(settingsState, config, "");
      },
      after: async () => {
        await refreshProviderState();
        await startProviderAuthLoginById(config.providerId);
      },
    });
  }

  async function startProviderAuthLoginById(providerId: string): Promise<void> {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    await runProviderAuthAction(settingsState, copy, config, config.loginFailedNoticeKey, async () => {
      const payload = await requestProviderAuthLogin(requestSettingsJson, config);
      const nextAuth = {
        ...authStateForConfig(settingsState, config),
        ...config.normalizeLogin(payload),
      };
      setAuthStateForConfig(settingsState, config, nextAuth);
      const verificationUri = String(nextAuth.verificationUri || "");
      if (verificationUri) {
        window.open(verificationUri, "_blank", "noopener,noreferrer");
      }
      setSettingsSuccess(config.noticeKey, authNotice(copy, config.loginReadyNoticeKey));
      scheduleProviderAuthPollById(config.providerId);
    }, { clearNotice: true, before: () => clearProviderAuthPollTimer(config.providerId) });
  }

  async function pollProviderAuthLoginById(providerId: string): Promise<void> {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    const pendingAuth = authStateForConfig(settingsState, config);
    if (!config.hasPendingPoll(pendingAuth)) return;
    try {
      const payload = await requestProviderAuthPoll(requestSettingsJson, config, pendingAuth);
      if (payload.status === "authorized") {
        const auth = payload.auth || {};
        const currentAuth = authStateForConfig(settingsState, config);
        setAuthStateForConfig(settingsState, config, {
          ...currentAuth,
          ...config.normalizeAuthorized(auth, currentAuth),
        });
        setSettingsSuccess(config.noticeKey, authNotice(copy, config.loginCompleteNoticeKey));
        await loadModelSettings();
        return;
      }
      scheduleProviderAuthPollById(config.providerId);
    } catch (error: unknown) {
      setProviderAuthError(settingsState, copy, config, config.loginFailedNoticeKey, error);
      clearProviderAuthPollTimer(config.providerId);
    }
  }

  async function logoutProviderAuthById(providerId: string): Promise<void> {
    const config = getProviderAuthConfig(providerAuthConfigs, providerId);
    await runProviderAuthAction(settingsState, copy, config, config.logoutFailedNoticeKey, async () => {
      await requestProviderAuthLogout(requestSettingsJson, config);
      setAuthStateForConfig(settingsState, config, config.resetLogout(authStateForConfig(settingsState, config)));
      setSettingsSuccess(config.noticeKey, authNotice(copy, config.loggedOutNoticeKey));
    }, {
      clearNotice: true,
      before: () => clearProviderAuthPollTimer(config.providerId),
      after: () => loadProviderAuthStatusById(config.providerId),
    });
  }

  function clearProviderAuthPollTimers(): void {
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
