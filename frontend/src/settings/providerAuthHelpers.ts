import {
  PROVIDER_AUTH_SECTION_CONFIGS,
  providerAuthSectionForId,
  type ProviderAuthSectionConfig,
} from "./providerAuthMetadata";
import type { ProviderAuthInitialStates } from "./providerAuthInitialState";
import { hasConnectedProvider, providerCatalogKey, type ProviderLike } from "./providerHelpers";
import { toPayloadSource } from "../composables/payloadBoundary";
import type { ProviderAuthStatePayload } from "../composables/providerAuthState";

export type ProviderAuthSlotState = ProviderAuthInitialStates & {
  providers?: {
    connected?: unknown;
  };
};
type ProviderAuthCopyRootPayload = {
  settings?: unknown;
};
type ProviderAuthSettingsCopyPayload = {
  providers?: unknown;
};
type ProviderAuthCopyKey = ProviderAuthSectionConfig["copyKey"];
type ProviderAuthProviderCopyMap = {
  [CopyKey in ProviderAuthCopyKey]?: unknown;
};
export type ProviderAuthConfigView = Pick<
  ProviderAuthSectionConfig,
  "providerId" | "stateKey" | "loadingKey" | "errorKey" | "noticeKey" | "copyKey"
>;
export type ProviderAuthStateView = Pick<
  ProviderAuthStatePayload,
  "configured" | "userCode" | "expired" | "account_id" | "expires_at" | "path" | "verificationUri"
>;
export type ProviderAuthCopyView = {
  login?: unknown;
  logout?: unknown;
  loading?: unknown;
  notConfigured?: unknown;
  configured?: unknown;
  expired?: unknown;
  description?: unknown;
  configuredDescription?: unknown;
  account?: unknown;
  expires?: unknown;
  path?: unknown;
  providerNeedsLogin?: unknown;
  name?: unknown;
  openVerification?: unknown;
  refresh?: unknown;
  title?: unknown;
  userCodeLabel?: unknown;
};

export function isOAuthProviderAuthType(authType: string): boolean {
  return PROVIDER_AUTH_SECTION_CONFIGS.some((config) => config.oauthAuthType === authType);
}

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

function providerAuthSection(provider: ProviderLike | null | undefined): ProviderAuthConfigView | undefined {
  return providerAuthSectionForId(providerCatalogKey(provider));
}

export function authState(state: ProviderAuthSlotState, config: ProviderAuthConfigView): ProviderAuthStateView {
  return state[config.stateKey];
}

export function authCopyForConfig(copy: unknown, config: ProviderAuthConfigView): ProviderAuthCopyView {
  const root = toPayloadSource<ProviderAuthCopyRootPayload>(copy);
  const settings = toPayloadSource<ProviderAuthSettingsCopyPayload>(root?.settings);
  const providers = toPayloadSource<ProviderAuthProviderCopyMap>(settings?.providers);
  return toPayloadSource<ProviderAuthCopyView>(providers?.[config.copyKey]) || {};
}

function formattedPart(formatter: unknown, value: unknown): string {
  return typeof formatter === "function" && value ? String(formatter(value)) : "";
}

export function providerAuthVisible(state: ProviderAuthSlotState, config: ProviderAuthConfigView): boolean {
  const auth = authState(state, config);
  return Boolean(
    hasConnectedProvider(state, config.providerId)
      || state[config.loadingKey]
      || auth.configured
      || auth.userCode
      || state[config.noticeKey]
      || state[config.errorKey],
  );
}

export function providerAuthCopyKey(provider: ProviderLike | null | undefined): string {
  return providerAuthSection(provider)?.copyKey || "";
}

export function providerAuthCopyForProvider(
  copy: unknown,
  provider: ProviderLike | null | undefined,
): ProviderAuthCopyView {
  const config = providerAuthSection(provider);
  return config ? authCopyForConfig(copy, config) : {};
}

export function providerAuthConfigured(state: ProviderAuthSlotState, provider: ProviderLike | null | undefined): boolean {
  const config = providerAuthSection(provider);
  return !config || Boolean(authState(state, config).configured);
}

export function authStatusLabel(copy: ProviderAuthCopyView = {}, auth: ProviderAuthStateView = {}, loading = false): string {
  if (loading) {
    return text(copy.loading, "Loading");
  }
  if (!auth.configured) {
    return text(copy.notConfigured, "Not configured");
  }
  if (auth.expired) {
    return text(copy.expired, "Expired");
  }
  return text(copy.configured, "Configured");
}

export function providerAuthDescription(copy: unknown, state: ProviderAuthSlotState, config: ProviderAuthConfigView): string {
  const auth = authState(state, config);
  const authCopy = authCopyForConfig(copy, config);
  if (!auth.configured) {
    return text(authCopy.description);
  }
  const parts = [
    formattedPart(authCopy.account, auth.account_id),
    formattedPart(authCopy.expires, auth.expires_at),
    formattedPart(authCopy.path, auth.path),
  ].filter(Boolean);
  return parts.join(" - ") || text(authCopy.configuredDescription);
}

export function providerDescription(copy: unknown, state: ProviderAuthSlotState, provider: ProviderLike | null | undefined): string {
  const authConfig = providerAuthSection(provider);
  if (authConfig && !authState(state, authConfig).configured) {
    return text(authCopyForConfig(copy, authConfig).providerNeedsLogin || provider?.base_url);
  }
  return text(provider?.base_url || provider?.description);
}
