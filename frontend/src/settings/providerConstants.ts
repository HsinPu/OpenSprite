export const CODEX_PROVIDER_ID = "openai-codex";
export const COPILOT_PROVIDER_ID = "copilot";

export const CODEX_AUTH_KEY = "codexAuth";
export const COPILOT_AUTH_KEY = "copilotAuth";

export function providerAuthEndpoint(providerId: string, action = "") {
  return `/api/settings/auth/${providerId}${action ? `/${action}` : ""}`;
}
