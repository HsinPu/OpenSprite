import type { ProviderCredentialView, ProviderCredentialsState } from "../composables/useSettingsState";
import { providerCatalogKey, type ProviderLike } from "./providerHelpers";
import { toPayloadSource } from "../composables/payloadBoundary";

type CredentialCopyRootPayload = {
  settings?: unknown;
};
type CredentialSettingsCopyPayload = {
  providers?: unknown;
};
type CredentialProvidersCopyPayload = {
  credentialSources?: unknown;
};
const CREDENTIAL_SOURCES = ["explicit", "provider_default", "priority"] as const;
type CredentialSource = (typeof CREDENTIAL_SOURCES)[number];
type CredentialSourceMapPayload = {
  [Source in CredentialSource]?: unknown;
};
type CredentialProvider = ProviderLike & {
  credential_effective_id?: unknown;
  effective_credential_id?: unknown;
  credential_id?: unknown;
  credential_source?: unknown;
};
type CredentialSettingsState = {
  credentials?: ProviderCredentialsState;
};

function credentialList(value: unknown): ProviderCredentialView[] {
  return Array.isArray(value)
    ? value.filter((credential): credential is ProviderCredentialView => credential !== null && typeof credential === "object" && !Array.isArray(credential))
    : [];
}

function credentialSource(value: unknown): CredentialSource | null {
  const source = String(value || "");
  return source === "explicit" || source === "provider_default" || source === "priority"
    ? source
    : null;
}

export function providerCredentials(state: CredentialSettingsState, provider: CredentialProvider | null | undefined): ProviderCredentialView[] {
  const providerKey = providerCatalogKey(provider);
  return credentialList(state.credentials?.[providerKey]);
}

export function providerEffectiveCredentialId(provider: CredentialProvider | null | undefined): string {
  return String(provider?.credential_effective_id || provider?.effective_credential_id || provider?.credential_id || "");
}

export function credentialSourceLabel(copy: unknown, provider: CredentialProvider | null | undefined): string {
  const root = toPayloadSource<CredentialCopyRootPayload>(copy);
  const settings = toPayloadSource<CredentialSettingsCopyPayload>(root?.settings);
  const providers = toPayloadSource<CredentialProvidersCopyPayload>(settings?.providers);
  const sources = toPayloadSource<CredentialSourceMapPayload>(providers?.credentialSources) || {};
  const source = credentialSource(provider?.credential_source);
  return source ? String(sources[source] || "") : "";
}
