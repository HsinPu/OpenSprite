import {
  DEFAULT_PROVIDER_AUTH_PROVIDER_ID,
  PROVIDER_AUTH_SECTION_CONFIGS,
  providerAuthStateKeys,
  providerAuthSectionForId,
  type ProviderAuthProviderId,
} from "../settings/providerAuthMetadata";
import type {
  ProviderAuthLoadingKey,
  ProviderAuthMessageKey,
  ProviderAuthStateKey,
} from "../settings/providerAuthInitialState";
import { providerAuthEndpoint } from "../settings/providerEndpoints";
import {
  clearedDeviceAuthState,
  normalizeDeviceAuthLogin,
  type ProviderAuthDeviceKey,
  type ProviderAuthPendingPayload,
  type ProviderAuthStatePayload,
  type ProviderAuthStatusPayload,
  type ProviderDeviceAuthPayloadDeviceKey,
  type ProviderDeviceAuthLoginPayload,
} from "./providerAuthState";

type ProviderAuthStateKeys = Omit<
  ReturnType<typeof providerAuthStateKeys>,
  "stateKey" | "loadingKey" | "errorKey" | "noticeKey"
> & {
  stateKey: ProviderAuthStateKey;
  loadingKey: ProviderAuthLoadingKey;
  errorKey: ProviderAuthMessageKey;
  noticeKey: ProviderAuthMessageKey;
};
type ProviderAuthPollRequestPayload = {
  device_auth_id?: string;
  device_code?: string;
  user_code?: string;
};
type ProviderAuthSectionConfig = ProviderAuthStateKeys & {
  providerId: string;
  deviceKey: ProviderAuthDeviceKey;
  payloadDeviceKey: ProviderDeviceAuthPayloadDeviceKey;
  pollRequiresUserCode?: boolean;
  includeAccountStatus?: boolean;
  loginExtra?: ProviderAuthStatePayload;
  logoutReset?: ProviderAuthStatePayload;
};
type ProviderAuthActionMetadata = ProviderAuthStateKeys & {
  providerId: string;
  endpoint: string;
  loginEndpoint: string;
  logoutEndpoint: string;
  pollEndpoint: string;
};
export type ProviderAuthConfig = ProviderAuthActionMetadata & {
  hasPendingPoll: (auth: ProviderAuthPendingPayload) => boolean;
  buildPollBody: (auth: ProviderAuthPendingPayload) => ProviderAuthPollRequestPayload;
  normalizeLogin: (payload: ProviderDeviceAuthLoginPayload) => ProviderAuthPendingPayload;
  normalizeStatus: (payload: ProviderAuthStatusPayload) => ProviderAuthStatePayload;
  normalizeAuthorized: (auth: ProviderAuthStatusPayload, currentAuth: ProviderAuthStatePayload) => ProviderAuthStatePayload;
  resetLogout: (auth: ProviderAuthStatePayload) => ProviderAuthStatePayload;
};
export type ProviderAuthConfigMap = {
  [ProviderId in ProviderAuthProviderId]: ProviderAuthConfig;
};

function optionalText(value: unknown): string {
  return String(value || "").trim();
}

function optionalNullableText(value: unknown): string | null {
  return optionalText(value) || null;
}

function providerAuthActionConfig(config: ProviderAuthSectionConfig): ProviderAuthActionMetadata {
  const providerId = config.providerId;
  const actionKeys: ProviderAuthStateKeys = {
    stateKey: config.stateKey,
    loadingKey: config.loadingKey,
    errorKey: config.errorKey,
    noticeKey: config.noticeKey,
    connectedNoticeKey: config.connectedNoticeKey,
    loadFailedNoticeKey: config.loadFailedNoticeKey,
    loginReadyNoticeKey: config.loginReadyNoticeKey,
    loginFailedNoticeKey: config.loginFailedNoticeKey,
    loginCompleteNoticeKey: config.loginCompleteNoticeKey,
    loggedOutNoticeKey: config.loggedOutNoticeKey,
    logoutFailedNoticeKey: config.logoutFailedNoticeKey,
  };
  return {
    ...actionKeys,
    providerId,
    endpoint: providerAuthEndpoint(providerId),
    loginEndpoint: providerAuthEndpoint(providerId, "login"),
    logoutEndpoint: providerAuthEndpoint(providerId, "logout"),
    pollEndpoint: providerAuthEndpoint(providerId, "poll"),
  };
}

function normalizeAuthorizedDeviceAuth(
  auth: ProviderAuthStatusPayload,
  currentAuth: ProviderAuthStatePayload,
  deviceKey: ProviderAuthDeviceKey,
  extraAuth: ProviderAuthStatePayload = {},
): ProviderAuthStatePayload {
  return { configured: Boolean(auth.configured), ...extraAuth, path: optionalText(auth.path || currentAuth.path), ...clearedDeviceAuthState(deviceKey) };
}

function resetDeviceAuthLogout(
  auth: ProviderAuthStatePayload,
  deviceKey: ProviderAuthDeviceKey,
  resetState: ProviderAuthStatePayload = {},
): ProviderAuthStatePayload {
  return { ...auth, configured: false, ...resetState, ...clearedDeviceAuthState(deviceKey) };
}

function normalizeConfiguredPathStatus(
  payload: ProviderAuthStatusPayload,
  extra: ProviderAuthStatePayload = {},
): ProviderAuthStatePayload {
  return { configured: Boolean(payload.configured), ...extra, path: optionalText(payload.path) };
}

function normalizeProviderAccountStatus(config: ProviderAuthSectionConfig, payload: ProviderAuthStatusPayload): ProviderAuthStatePayload {
  return config.includeAccountStatus
    ? { expired: Boolean(payload.expired), expires_at: optionalNullableText(payload.expires_at), account_id: optionalText(payload.account_id) }
    : {};
}

function deviceAuthPollBody(config: ProviderAuthSectionConfig, auth: ProviderAuthPendingPayload): ProviderAuthPollRequestPayload {
  const body: ProviderAuthPollRequestPayload = {};
  if (config.payloadDeviceKey === "device_auth_id") {
    body.device_auth_id = auth[config.deviceKey];
  } else {
    body.device_code = auth[config.deviceKey];
  }
  if (config.pollRequiresUserCode && auth.userCode) {
    body.user_code = auth.userCode;
  }
  return body;
}

function deviceAuthPollConfig(config: ProviderAuthSectionConfig): Pick<ProviderAuthConfig, "hasPendingPoll" | "buildPollBody"> {
  return {
    hasPendingPoll: (auth: ProviderAuthPendingPayload) => Boolean(auth[config.deviceKey] && (!config.pollRequiresUserCode || auth.userCode)),
    buildPollBody: (auth: ProviderAuthPendingPayload) => deviceAuthPollBody(config, auth),
  };
}

function deviceAuthBaseConfig(config: ProviderAuthSectionConfig): ProviderAuthConfig {
  return {
    ...providerAuthActionConfig(config),
    ...deviceAuthPollConfig(config),
    normalizeLogin: (payload: ProviderDeviceAuthLoginPayload) => normalizeDeviceAuthLogin(payload, config.deviceKey, config.payloadDeviceKey, config.loginExtra),
    normalizeStatus: (payload: ProviderAuthStatusPayload) => normalizeConfiguredPathStatus(payload, normalizeProviderAccountStatus(config, payload)),
    normalizeAuthorized: (auth: ProviderAuthStatusPayload, currentAuth: ProviderAuthStatePayload) => normalizeAuthorizedDeviceAuth(auth, currentAuth, config.deviceKey, normalizeProviderAccountStatus(config, auth)),
    resetLogout: (auth: ProviderAuthStatePayload) => resetDeviceAuthLogout(auth, config.deviceKey, config.logoutReset),
  };
}

export function createProviderAuthConfigs(): ProviderAuthConfigMap {
  const [openaiCodexConfig, copilotConfig] = PROVIDER_AUTH_SECTION_CONFIGS;
  return {
    [openaiCodexConfig.providerId]: deviceAuthBaseConfig(openaiCodexConfig),
    [copilotConfig.providerId]: deviceAuthBaseConfig(copilotConfig),
  };
}

export function getProviderAuthConfig(
  providerAuthConfigs: ProviderAuthConfigMap,
  providerId: string,
): ProviderAuthConfig {
  const section = providerAuthSectionForId(providerId);
  return providerAuthConfigs[section?.providerId ?? DEFAULT_PROVIDER_AUTH_PROVIDER_ID];
}
