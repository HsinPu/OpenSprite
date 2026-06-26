import { type AnyRecord, providerCatalogKey } from "./providerHelpers";

export function providerCredentials(state: AnyRecord, provider: AnyRecord) {
  const providerKey = providerCatalogKey(provider);
  return state.credentials?.[providerKey] || [];
}

export function providerEffectiveCredentialId(provider: AnyRecord) {
  return provider?.credential_effective_id || provider?.effective_credential_id || provider?.credential_id || "";
}

export function credentialSourceLabel(copy: AnyRecord, provider: AnyRecord) {
  const sources = copy.settings.providers?.credentialSources || {};
  return sources[provider?.credential_source] || "";
}
