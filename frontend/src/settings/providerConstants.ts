export const CODEX_PROVIDER_ID = "openai-codex";
export const COPILOT_PROVIDER_ID = "copilot";

export const CODEX_PROVIDER_NAME = "OpenAI Codex";
export const COPILOT_PROVIDER_NAME = "GitHub Copilot";

export const CODEX_AUTH_KEY = "codexAuth";
export const COPILOT_AUTH_KEY = "copilotAuth";

export function providerAuthStateKeys(authKey: string) {
  return {
    authKey,
    copyKey: authKey,
    stateKey: authKey,
    loadingKey: `${authKey}Loading`,
    errorKey: `${authKey}Error`,
    noticeKey: `${authKey}Notice`,
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

export function providerAuthRequestConfig(providerId: string, keys: ReturnType<typeof providerAuthStateKeys>) {
  return {
    providerId,
    endpoint: providerAuthEndpoint(providerId),
    loginEndpoint: providerAuthEndpoint(providerId, "login"),
    logoutEndpoint: providerAuthEndpoint(providerId, "logout"),
    pollEndpoint: providerAuthEndpoint(providerId, "poll"),
    ...keys,
  };
}

export const CODEX_AUTH_STATE_KEYS = providerAuthStateKeys(CODEX_AUTH_KEY);
export const COPILOT_AUTH_STATE_KEYS = providerAuthStateKeys(COPILOT_AUTH_KEY);

export function createProviderAuthInitialStates() {
  return {
    ...providerAuthInitialState(CODEX_AUTH_STATE_KEYS, providerDeviceAuthInitialState("deviceAuthId", {
      expired: false,
      expires_at: null,
      account_id: "",
      command: "",
    })),
    ...providerAuthInitialState(COPILOT_AUTH_STATE_KEYS, providerDeviceAuthInitialState("deviceCode")),
  };
}

const PROVIDER_AUTH_KEYS: Record<string, string> = {
  [CODEX_PROVIDER_ID]: CODEX_AUTH_STATE_KEYS.authKey,
  [COPILOT_PROVIDER_ID]: COPILOT_AUTH_STATE_KEYS.authKey,
};

export const PROVIDER_AUTH_PROVIDER_IDS = Object.keys(PROVIDER_AUTH_KEYS);

export function providerAuthKeyForId(providerId: string) {
  return PROVIDER_AUTH_KEYS[providerId] || "";
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
