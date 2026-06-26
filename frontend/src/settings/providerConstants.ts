export const CODEX_PROVIDER_ID = "openai-codex";
export const COPILOT_PROVIDER_ID = "copilot";

export const CODEX_AUTH_KEY = "codexAuth";
export const COPILOT_AUTH_KEY = "copilotAuth";

export const OPENAI_CODEX_OAUTH_AUTH_TYPE = "openai_codex_oauth";
export const GITHUB_COPILOT_OAUTH_AUTH_TYPE = "github_copilot_oauth";

export function providerAuthEndpoint(providerId: string, action = "") {
  return `/api/settings/auth/${providerId}${action ? `/${action}` : ""}`;
}

export function isOAuthProviderAuthType(authType: string) {
  return authType === OPENAI_CODEX_OAUTH_AUTH_TYPE || authType === GITHUB_COPILOT_OAUTH_AUTH_TYPE;
}
