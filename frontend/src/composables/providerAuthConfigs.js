import {
  CODEX_PROVIDER_ID,
  COPILOT_PROVIDER_ID,
  DEFAULT_PROVIDER_AUTH_PROVIDER_ID,
  providerAuthRequestConfig,
  providerAuthSectionForId,
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

export function createProviderAuthConfigs() {
  const codexAuthConfig = providerAuthSectionForId(CODEX_PROVIDER_ID);
  const copilotAuthConfig = providerAuthSectionForId(COPILOT_PROVIDER_ID);

  return {
    [CODEX_PROVIDER_ID]: {
      ...providerAuthRequestConfig(codexAuthConfig),
      connectedNoticeKey: "codexProviderConnected",
      hasPendingPoll: (auth) => Boolean(auth[codexAuthConfig.deviceKey] && auth.userCode),
      buildPollBody: (auth) => ({ [codexAuthConfig.payloadDeviceKey]: auth[codexAuthConfig.deviceKey], user_code: auth.userCode }),
      normalizeStatus: (payload) => normalizeConfiguredPathStatus(payload, {
        expired: Boolean(payload.expired),
        expires_at: payload.expires_at || null,
        account_id: payload.account_id || "",
      }),
      normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, codexAuthConfig.deviceKey, codexAuthConfig.payloadDeviceKey, { command: "" }),
      normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, codexAuthConfig.deviceKey, {
        expired: Boolean(auth.expired),
        expires_at: auth.expires_at || null,
        account_id: auth.account_id || "",
      }),
      resetLogout: (auth) => resetDeviceAuthLogout(auth, codexAuthConfig.deviceKey, {
        expired: false,
        expires_at: null,
        account_id: "",
        command: "",
      }),
    },
    [COPILOT_PROVIDER_ID]: {
      ...providerAuthRequestConfig(copilotAuthConfig),
      connectedNoticeKey: "copilotProviderConnected",
      hasPendingPoll: (auth) => Boolean(auth[copilotAuthConfig.deviceKey]),
      buildPollBody: (auth) => ({ [copilotAuthConfig.payloadDeviceKey]: auth[copilotAuthConfig.deviceKey] }),
      normalizeStatus: normalizeConfiguredPathStatus,
      normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, copilotAuthConfig.deviceKey, copilotAuthConfig.payloadDeviceKey),
      normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, copilotAuthConfig.deviceKey),
      resetLogout: (auth) => resetDeviceAuthLogout(auth, copilotAuthConfig.deviceKey, { path: "" }),
    },
  };
}

function resolveProviderAuthConfigId(providerAuthConfigs, providerId) {
  return providerAuthConfigs[providerId] ? providerId : DEFAULT_PROVIDER_AUTH_PROVIDER_ID;
}

export function getProviderAuthConfig(providerAuthConfigs, providerId) {
  return providerAuthConfigs[resolveProviderAuthConfigId(providerAuthConfigs, providerId)];
}
