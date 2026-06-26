import { PROVIDER_AUTH_SECTION_CONFIGS, providerAuthSectionForId } from "./providerAuthMetadata";
import { type AnyRecord, hasConnectedProvider, providerCatalogKey } from "./providerHelpers";

export function isOAuthProviderAuthType(authType: string) {
  return PROVIDER_AUTH_SECTION_CONFIGS.some((config) => config.oauthAuthType === authType);
}

function providerAuthSection(provider: AnyRecord) {
  return providerAuthSectionForId(providerCatalogKey(provider));
}

export function providerAuthVisible(state: AnyRecord, config: AnyRecord) {
  const auth = state[config.stateKey] || {};
  return Boolean(hasConnectedProvider(state, config.providerId) || state[config.loadingKey] || auth?.configured || auth?.userCode || state[config.noticeKey] || state[config.errorKey]);
}

export function providerAuthCopyKey(provider: AnyRecord) {
  return providerAuthSection(provider)?.copyKey || "";
}

export function providerAuthConfigured(state: AnyRecord, provider: AnyRecord) {
  const config = providerAuthSection(provider);
  return !config || Boolean(state[config.stateKey]?.configured);
}

export function authStatusLabel(copy: AnyRecord = {}, auth: AnyRecord = {}, loading = false) {
  if (loading) {
    return copy.loading || "Loading";
  }
  if (!auth.configured) {
    return copy.notConfigured || "Not configured";
  }
  if (auth.expired) {
    return copy.expired || "Expired";
  }
  return copy.configured || "Configured";
}

export function providerAuthDescription(copy: AnyRecord, state: AnyRecord, config: AnyRecord) {
  const auth = state[config.stateKey] || {};
  const authCopy = copy.settings.providers?.[config.copyKey] || {};
  if (!auth.configured) {
    return authCopy.description || "";
  }
  const parts: string[] = [];
  if (auth.account_id && typeof authCopy.account === "function") {
    parts.push(authCopy.account(auth.account_id));
  }
  if (auth.expires_at && typeof authCopy.expires === "function") {
    parts.push(authCopy.expires(auth.expires_at));
  }
  if (auth.path && typeof authCopy.path === "function") {
    parts.push(authCopy.path(auth.path));
  }
  return parts.join(" - ") || authCopy.configuredDescription || "";
}

export function providerDescription(copy: AnyRecord, state: AnyRecord, provider: AnyRecord) {
  const providerCopy = copy.settings.providers || {};
  const authConfig = providerAuthSection(provider);
  if (authConfig && !state[authConfig.stateKey]?.configured) {
    return providerCopy[authConfig.copyKey]?.providerNeedsLogin || provider.base_url || "";
  }
  return provider?.base_url || provider?.description || "";
}
