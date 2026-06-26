export const CODEX_PROVIDER_ID = "openai-codex";
export const COPILOT_PROVIDER_ID = "copilot";

export const CODEX_PROVIDER_NAME = "OpenAI Codex";
export const COPILOT_PROVIDER_NAME = "GitHub Copilot";

const CODEX_AUTH_KEY = "codexAuth";
const COPILOT_AUTH_KEY = "copilotAuth";

export function providerAuthStateKeys(authKey: string) {
  return {
    authKey,
    copyKey: authKey,
    stateKey: authKey,
    loadingKey: `${authKey}Loading`,
    errorKey: `${authKey}Error`,
    noticeKey: `${authKey}Notice`,
    connectedNoticeKey: authKey.replace(/Auth$/, "ProviderConnected"),
    loadFailedNoticeKey: `${authKey}LoadFailed`,
    loginReadyNoticeKey: `${authKey}LoginReady`,
    loginFailedNoticeKey: `${authKey}LoginFailed`,
    loginCompleteNoticeKey: `${authKey}LoginComplete`,
    loggedOutNoticeKey: `${authKey}LoggedOut`,
    logoutFailedNoticeKey: `${authKey}LogoutFailed`,
  };
}

export function providerAuthInitialState(keys: ReturnType<typeof providerAuthStateKeys>, auth: Record<string, unknown>) {
  return {
    [keys.loadingKey]: false,
    [keys.errorKey]: "",
    [keys.noticeKey]: "",
    [keys.authKey]: auth,
  };
}

function providerDeviceAuthInitialState(deviceKey: string, extra: Record<string, unknown> = {}) {
  return { configured: false, path: "", verificationUri: "", userCode: "", pollIntervalSeconds: 5, ...extra, [deviceKey]: "" };
}

const PROVIDER_AUTH_REQUEST_KEYS = Object.keys(providerAuthStateKeys("")) as Array<keyof ReturnType<typeof providerAuthStateKeys>>;

export function providerAuthRequestConfig(config: ReturnType<typeof providerAuthStateKeys> & { providerId: string }) {
  const { providerId } = config;
  return {
    providerId,
    endpoint: providerAuthEndpoint(providerId),
    loginEndpoint: providerAuthEndpoint(providerId, "login"),
    logoutEndpoint: providerAuthEndpoint(providerId, "logout"),
    pollEndpoint: providerAuthEndpoint(providerId, "poll"),
    ...Object.fromEntries(PROVIDER_AUTH_REQUEST_KEYS.map((key) => [key, config[key]])),
  };
}

const CODEX_AUTH_STATE_KEYS = providerAuthStateKeys(CODEX_AUTH_KEY);
const COPILOT_AUTH_STATE_KEYS = providerAuthStateKeys(COPILOT_AUTH_KEY);

export const PROVIDER_AUTH_SECTION_CONFIGS = [
  {
    providerId: CODEX_PROVIDER_ID, ...CODEX_AUTH_STATE_KEYS, mark: "Cx", providerName: CODEX_PROVIDER_NAME,
    deviceKey: "deviceAuthId", payloadDeviceKey: "device_auth_id",
    pollRequiresUserCode: true,
    includeAccountStatus: true,
    loginExtra: { command: "" },
    logoutReset: { expired: false, expires_at: null, account_id: "", command: "" },
    initialAuth: providerDeviceAuthInitialState("deviceAuthId", { expired: false, expires_at: null, account_id: "", command: "" }),
  },
  {
    providerId: COPILOT_PROVIDER_ID, ...COPILOT_AUTH_STATE_KEYS, mark: "Gh", providerName: COPILOT_PROVIDER_NAME,
    deviceKey: "deviceCode", payloadDeviceKey: "device_code",
    logoutReset: { path: "" },
    initialAuth: providerDeviceAuthInitialState("deviceCode"),
  },
];

export const DEFAULT_PROVIDER_AUTH_PROVIDER_ID = PROVIDER_AUTH_SECTION_CONFIGS[0].providerId;

export function createProviderAuthInitialStates() {
  return Object.assign(
    {},
    ...PROVIDER_AUTH_SECTION_CONFIGS.map((config) => providerAuthInitialState(config, config.initialAuth)),
  );
}

const PROVIDER_AUTH_SECTIONS = Object.fromEntries(PROVIDER_AUTH_SECTION_CONFIGS.map((config) => [config.providerId, config]));

export const PROVIDER_AUTH_PROVIDER_IDS = Object.keys(PROVIDER_AUTH_SECTIONS);

export function providerAuthSectionForId(providerId: string) {
  return PROVIDER_AUTH_SECTIONS[providerId];
}

export function providerAuthKeyForId(providerId: string) {
  return providerAuthSectionForId(providerId)?.authKey || "";
}

export const OPENAI_CODEX_OAUTH_AUTH_TYPE = "openai_codex_oauth";
export const GITHUB_COPILOT_OAUTH_AUTH_TYPE = "github_copilot_oauth";

export function providerAuthEndpoint(providerId: string, action = "") {
  return `/api/settings/auth/${providerId}${action ? `/${action}` : ""}`;
}

export function providerSettingsEndpoint(providerId: string, action = "") {
  return `/api/settings/providers/${encodeURIComponent(providerId)}${action ? `/${action}` : ""}`;
}

export function providerCredentialEndpoint(providerKey: string, credentialId: string) {
  return `/api/settings/credentials/${encodeURIComponent(providerKey)}/${encodeURIComponent(credentialId)}`;
}

export function isOAuthProviderAuthType(authType: string) {
  return authType === OPENAI_CODEX_OAUTH_AUTH_TYPE || authType === GITHUB_COPILOT_OAUTH_AUTH_TYPE;
}
