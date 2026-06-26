import {
  CODEX_AUTH_STATE_KEYS,
  CODEX_PROVIDER_ID,
  CODEX_PROVIDER_NAME,
  COPILOT_AUTH_STATE_KEYS,
  COPILOT_PROVIDER_ID,
  COPILOT_PROVIDER_NAME,
  providerAuthRequestConfig,
} from "../settings/providerConstants";
import { clearedDeviceAuthState, normalizeDeviceAuthLogin } from "./providerAuthState";

export function createProviderAuthRuntimeConfigs({
  copy,
  startAuthLoginById,
  clearProviderAuthPollTimer,
  scheduleProviderAuthPollById,
  loadProviderAuthStatusById,
}) {
  const runtimeConfig = (providerId, providerName, connectedNoticeKey) => ({
    providerName,
    connectedNotice: () => copy.value.notices[connectedNoticeKey],
    startAuthLogin: () => startAuthLoginById(providerId),
    clearPoll: () => clearProviderAuthPollTimer(providerId),
    schedulePoll: () => scheduleProviderAuthPollById(providerId),
    loadStatus: () => loadProviderAuthStatusById(providerId),
  });
  return {
    [CODEX_PROVIDER_ID]: runtimeConfig(CODEX_PROVIDER_ID, CODEX_PROVIDER_NAME, "codexProviderConnected"),
    [COPILOT_PROVIDER_ID]: runtimeConfig(COPILOT_PROVIDER_ID, COPILOT_PROVIDER_NAME, "copilotProviderConnected"),
  };
}

export function createProviderAuthConfigs(runtimeConfigs = {}) {
  return {
    [CODEX_PROVIDER_ID]: {
      ...providerAuthRequestConfig(CODEX_PROVIDER_ID, CODEX_AUTH_STATE_KEYS),
      ...(runtimeConfigs[CODEX_PROVIDER_ID] || {}),
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
        ...clearedDeviceAuthState("deviceAuthId"),
      }),
      resetLogout: (auth) => ({
        ...auth,
        configured: false,
        expired: false,
        expires_at: null,
        account_id: "",
        command: "",
        ...clearedDeviceAuthState("deviceAuthId"),
      }),
    },
    [COPILOT_PROVIDER_ID]: {
      ...providerAuthRequestConfig(COPILOT_PROVIDER_ID, COPILOT_AUTH_STATE_KEYS),
      ...(runtimeConfigs[COPILOT_PROVIDER_ID] || {}),
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
        ...clearedDeviceAuthState("deviceCode"),
      }),
      resetLogout: (auth) => ({ ...auth, configured: false, path: "", ...clearedDeviceAuthState("deviceCode") }),
    },
  };
}

function resolveProviderAuthConfigId(providerAuthConfigs, providerId) {
  return providerAuthConfigs[providerId] ? providerId : CODEX_PROVIDER_ID;
}

export function getProviderAuthConfig(providerAuthConfigs, providerId) {
  return providerAuthConfigs[resolveProviderAuthConfigId(providerAuthConfigs, providerId)];
}
