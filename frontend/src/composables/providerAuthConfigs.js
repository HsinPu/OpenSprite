import {
  DEFAULT_PROVIDER_AUTH_PROVIDER_ID,
  PROVIDER_AUTH_SECTION_CONFIGS,
  providerAuthStateKeys,
} from "../settings/providerAuthMetadata";
import { providerAuthEndpoint } from "../settings/providerEndpoints";
import { clearedDeviceAuthState, normalizeDeviceAuthLogin } from "./providerAuthState";

const PROVIDER_AUTH_ACTION_KEYS = Object.keys(providerAuthStateKeys(""));

function providerAuthActionConfig(config) {
  const { providerId } = config;
  return {
    providerId,
    endpoint: providerAuthEndpoint(providerId),
    loginEndpoint: providerAuthEndpoint(providerId, "login"),
    logoutEndpoint: providerAuthEndpoint(providerId, "logout"),
    pollEndpoint: providerAuthEndpoint(providerId, "poll"),
    ...Object.fromEntries(PROVIDER_AUTH_ACTION_KEYS.map((key) => [key, config[key]])),
  };
}

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
    ...providerAuthActionConfig(config),
    ...deviceAuthPollConfig(config),
    normalizeLogin: (payload) => normalizeDeviceAuthLogin(payload, config.deviceKey, config.payloadDeviceKey, config.loginExtra),
    normalizeStatus: (payload) => normalizeConfiguredPathStatus(payload, normalizeProviderAccountStatus(config, payload)),
    normalizeAuthorized: (auth, currentAuth) => normalizeAuthorizedDeviceAuth(auth, currentAuth, config.deviceKey, normalizeProviderAccountStatus(config, auth)),
    resetLogout: (auth) => resetDeviceAuthLogout(auth, config.deviceKey, config.logoutReset),
  };
}

export function createProviderAuthConfigs() {
  return Object.fromEntries(
    PROVIDER_AUTH_SECTION_CONFIGS.map((config) => [config.providerId, deviceAuthBaseConfig(config)]),
  );
}

export function getProviderAuthConfig(providerAuthConfigs, providerId) {
  return providerAuthConfigs[providerId] || providerAuthConfigs[DEFAULT_PROVIDER_AUTH_PROVIDER_ID];
}
