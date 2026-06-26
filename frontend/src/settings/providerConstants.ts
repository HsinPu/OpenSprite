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

export const CODEX_AUTH_STATE_KEYS = providerAuthStateKeys(CODEX_AUTH_KEY);
export const COPILOT_AUTH_STATE_KEYS = providerAuthStateKeys(COPILOT_AUTH_KEY);

export const OPENAI_CODEX_OAUTH_AUTH_TYPE = "openai_codex_oauth";
export const GITHUB_COPILOT_OAUTH_AUTH_TYPE = "github_copilot_oauth";

export function providerAuthEndpoint(providerId: string, action = "") {
  return `/api/settings/auth/${providerId}${action ? `/${action}` : ""}`;
}

export function isOAuthProviderAuthType(authType: string) {
  return authType === OPENAI_CODEX_OAUTH_AUTH_TYPE || authType === GITHUB_COPILOT_OAUTH_AUTH_TYPE;
}
