import {
  CODEX_PROVIDER_ID,
  COPILOT_PROVIDER_ID,
  PROVIDER_AUTH_SECTION_CONFIGS,
  providerAuthRequestConfig,
} from "../settings/providerConstants";
import { clearedDeviceAuthState, normalizeDeviceAuthLogin } from "./providerAuthState";

function normalizeAuthorizedDeviceAuth(auth, currentAuth, deviceKey, extraAuth = {}) {
  return { configured: Boolean(auth.configured), ...extraAuth, path: auth.path || currentAuth.path, ...clearedDeviceAuthState(deviceKey) };
}

function resetDeviceAuthLogout(auth, deviceKey, resetState = {}) {
  return { ...auth, configured: false, ...resetState, ...clearedDeviceAuthState(deviceKey) };
}

function normalizeConfiguredPathStatus(payload, extra = {}) {
  return { configured: Boolean(payload.configured), ...extra, path: payload.path || "" };
}

const PROVIDER_AUTH_SECTIONS = Object.fromEntries(PROVIDER_AUTH_SECTION_CONFIGS.map((config) => [config.providerId, config]));

export function createProviderAuthConfigs() {
  return {
    [CODEX_PROVIDER_ID]: {
      ...providerAuthRequestConfig(PROVIDER_AUTH_SECTIONS[CODEX_PROVIDER_ID]),
      connectedNoticeKey: "codexProviderConnected",
      hasPendingPoll: (auth) => Boolean(auth.deviceAuthId && auth.userCode),
      buildPollBody: (auth) => ({ device_auth_id: auth.deviceAuthId, user_code: auth.userCode }),
      normalizeStatus: (payload) => normalizeConfiguredPathStatus(payload, {
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
      }),
      normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, "deviceAuthId", "device_auth_id", { command: "" }),
      normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, "deviceAuthId", {
        expired: Boolean(auth.expired),
        expires_at: auth.expires_at || null,
        account_id: auth.account_id || "",
      }),
      resetLogout: (auth) => resetDeviceAuthLogout(auth, "deviceAuthId", {
        expired: false,
        expires_at: null,
        account_id: "",
        command: "",
      }),
    },
    [COPILOT_PROVIDER_ID]: {
      ...providerAuthRequestConfig(PROVIDER_AUTH_SECTIONS[COPILOT_PROVIDER_ID]),
      connectedNoticeKey: "copilotProviderConnected",
      hasPendingPoll: (auth) => Boolean(auth.deviceCode),
      buildPollBody: (auth) => ({ device_code: auth.deviceCode }),
      normalizeStatus: normalizeConfiguredPathStatus,
      normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, "deviceCode", "device_code"),
      normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, "deviceCode"),
      resetLogout: (auth) => resetDeviceAuthLogout(auth, "deviceCode", { path: "" }),
    },
  };
}

function resolveProviderAuthConfigId(providerAuthConfigs, providerId) {
  return providerAuthConfigs[providerId] ? providerId : CODEX_PROVIDER_ID;
}

export function getProviderAuthConfig(providerAuthConfigs, providerId) {
  return providerAuthConfigs[resolveProviderAuthConfigId(providerAuthConfigs, providerId)];
}
