import type {
  ProviderAuthDeviceKey,
  ProviderAuthStatePayload,
} from "../composables/providerAuthState";

export function providerAuthStateKeys<const AuthKey extends string>(authKey: AuthKey) {
  return {
    stateKey: authKey,
    loadingKey: `${authKey}Loading` as const,
    errorKey: `${authKey}Error` as const,
    noticeKey: `${authKey}Notice` as const,
    connectedNoticeKey: authKey.replace(/Auth$/, "ProviderConnected"),
    loadFailedNoticeKey: `${authKey}LoadFailed`,
    loginReadyNoticeKey: `${authKey}LoginReady`,
    loginFailedNoticeKey: `${authKey}LoginFailed`,
    loginCompleteNoticeKey: `${authKey}LoginComplete`,
    loggedOutNoticeKey: `${authKey}LoggedOut`,
    logoutFailedNoticeKey: `${authKey}LogoutFailed`,
  };
}

function providerAuthSectionKeys<const AuthKey extends string>(authKey: AuthKey) {
  return { copyKey: authKey, ...providerAuthStateKeys(authKey) };
}

function providerDeviceAuthInitialState(deviceKey: ProviderAuthDeviceKey, extra: ProviderAuthStatePayload = {}): ProviderAuthStatePayload {
  const deviceState = deviceKey === "deviceAuthId"
    ? { deviceAuthId: "" }
    : { deviceCode: "" };
  return { configured: false, path: "", verificationUri: "", userCode: "", pollIntervalSeconds: 5, ...extra, ...deviceState };
}

export const PROVIDER_AUTH_SECTION_CONFIGS = [
  {
    providerId: "openai-codex", ...providerAuthSectionKeys("codexAuth"), mark: "Cx", providerName: "OpenAI Codex", oauthAuthType: "openai_codex_oauth",
    deviceKey: "deviceAuthId", payloadDeviceKey: "device_auth_id" as const,
    pollRequiresUserCode: true,
    includeAccountStatus: true,
    loginExtra: { command: "" },
    logoutReset: { expired: false, expires_at: null, account_id: "", command: "" },
    initialAuth: providerDeviceAuthInitialState("deviceAuthId", { expired: false, expires_at: null, account_id: "", command: "" }),
  },
  {
    providerId: "copilot", ...providerAuthSectionKeys("copilotAuth"), mark: "Gh", providerName: "GitHub Copilot", oauthAuthType: "github_copilot_oauth",
    deviceKey: "deviceCode", payloadDeviceKey: "device_code" as const,
    logoutReset: { path: "" },
    initialAuth: providerDeviceAuthInitialState("deviceCode"),
  },
] as const;

export type ProviderAuthSectionConfig = (typeof PROVIDER_AUTH_SECTION_CONFIGS)[number];
export type ProviderAuthProviderId = ProviderAuthSectionConfig["providerId"];

export const DEFAULT_PROVIDER_AUTH_PROVIDER_ID = PROVIDER_AUTH_SECTION_CONFIGS[0].providerId;

export const PROVIDER_AUTH_PROVIDER_IDS = PROVIDER_AUTH_SECTION_CONFIGS.map((config) => config.providerId);

export function providerAuthSectionForId(providerId: string): ProviderAuthSectionConfig | undefined {
  return PROVIDER_AUTH_SECTION_CONFIGS.find((config) => config.providerId === providerId);
}
