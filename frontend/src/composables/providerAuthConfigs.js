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

function normalizeProviderAccountStatus(config, payload) {
  return config.includeAccountStatus ? { expired: Boolean(payload.expired), expires_at: payload.expires_at || null, account_id: payload.account_id || "" } : {};
}

function deviceAuthPollConfig(config) {
  return {
    hasPendingPoll: (auth) => Boolean(auth[config.deviceKey] && (!config.pollRequiresUserCode || auth.userCode)),
    buildPollBody: (auth) => ({ [config.payloadDeviceKey]: auth[config.deviceKey], ...(config.pollRequiresUserCode ? { user_code: auth.userCode } : {}) }),
  };
}

function deviceAuthBaseConfig(config) {
  return {
    ...providerAuthRequestConfig(config),
    ...deviceAuthPollConfig(config),
    normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, config.deviceKey, config.payloadDeviceKey, config.loginExtra),
    resetLogout: (auth) => resetDeviceAuthLogout(auth, config.deviceKey, config.logoutReset),
  };
}

export function createProviderAuthConfigs() {
  const codexAuthConfig = providerAuthSectionForId(CODEX_PROVIDER_ID);
  const copilotAuthConfig = providerAuthSectionForId(COPILOT_PROVIDER_ID);

  return {
    [CODEX_PROVIDER_ID]: {
      ...deviceAuthBaseConfig(codexAuthConfig),
      normalizeStatus: (payload) => normalizeConfiguredPathStatus(payload, normalizeProviderAccountStatus(codexAuthConfig, payload)),
      normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, codexAuthConfig.deviceKey, normalizeProviderAccountStatus(codexAuthConfig, auth)),
    },
    [COPILOT_PROVIDER_ID]: {
      ...deviceAuthBaseConfig(copilotAuthConfig),
      normalizeStatus: normalizeConfiguredPathStatus,
      normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, copilotAuthConfig.deviceKey),
    },
  };
}

function resolveProviderAuthConfigId(providerAuthConfigs, providerId) {
  return providerAuthConfigs[providerId] ? providerId : DEFAULT_PROVIDER_AUTH_PROVIDER_ID;
}

export function getProviderAuthConfig(providerAuthConfigs, providerId) {
  return providerAuthConfigs[resolveProviderAuthConfigId(providerAuthConfigs, providerId)];
}
