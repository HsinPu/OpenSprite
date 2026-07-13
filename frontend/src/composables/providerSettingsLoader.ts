import type {
  ProviderCredentialView,
  ProviderCredentialsState,
  ProviderSettings,
  ProviderView,
} from "./useSettingsState";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type ProviderCredentialMapPayload = {
  [providerKey: string]: unknown;
};
type ProviderCredentialEntry = [string, unknown];
type ProviderSettingsPayload = {
  providers?: unknown;
  default_provider?: unknown;
  connected?: unknown;
  available?: unknown;
};
type ProviderCredentialsPayload = {
  credentials?: unknown;
};
type ProviderViewPayload = {
  id?: unknown;
  name?: unknown;
  provider?: unknown;
  providerName?: unknown;
  type?: unknown;
  auth_type?: unknown;
  base_url?: unknown;
  default_base_url?: unknown;
  description?: unknown;
  credential_id?: unknown;
  credential_effective_id?: unknown;
  effective_credential_id?: unknown;
  credential_label?: unknown;
  credential_preview?: unknown;
  connected_count?: unknown;
  api_key_optional?: unknown;
  requires_api_key?: unknown;
  is_default?: unknown;
  preset_name?: unknown;
};
type ProviderCredentialViewPayload = {
  id?: unknown;
  label?: unknown;
  name?: unknown;
  secret_preview?: unknown;
};

interface ProviderSettingsLoaderState {
  providersLoading: boolean;
  providersError: string;
  providers: ProviderSettings;
  credentials: ProviderCredentialsState;
}

interface ProviderSettingsLoaderCopy {
  notices: {
    providerLoadFailed: string;
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function toProviderSettingsPayload(value: unknown): ProviderSettingsPayload {
  const payload = toPayloadSource<ProviderSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    providers: payload.providers,
    default_provider: payload.default_provider,
    connected: payload.connected,
    available: payload.available,
  };
}

function toProviderCredentialsPayload(value: unknown): ProviderCredentialsPayload {
  const payload = toPayloadSource<ProviderCredentialsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    credentials: payload.credentials,
  };
}

function toProviderViewPayload(value: unknown): ProviderViewPayload {
  const payload = toPayloadSource<ProviderViewPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    id: payload.id,
    name: payload.name,
    provider: payload.provider,
    providerName: payload.providerName,
    type: payload.type,
    auth_type: payload.auth_type,
    base_url: payload.base_url,
    default_base_url: payload.default_base_url,
    description: payload.description,
    credential_id: payload.credential_id,
    credential_effective_id: payload.credential_effective_id,
    effective_credential_id: payload.effective_credential_id,
    credential_label: payload.credential_label,
    credential_preview: payload.credential_preview,
    connected_count: payload.connected_count,
    api_key_optional: payload.api_key_optional,
    requires_api_key: payload.requires_api_key,
    is_default: payload.is_default,
    preset_name: payload.preset_name,
  };
}

function toProviderCredentialViewPayload(value: unknown): ProviderCredentialViewPayload {
  const payload = toPayloadSource<ProviderCredentialViewPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    id: payload.id,
    label: payload.label,
    name: payload.name,
    secret_preview: payload.secret_preview,
  };
}

function optionalText(value: unknown): string | undefined {
  const text = String(value || "").trim();
  return text || undefined;
}

function optionalNumber(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : undefined;
}

function optionalBoolean(value: unknown): boolean | undefined {
  return value === undefined ? undefined : Boolean(value);
}

function toProviderView(value: unknown): ProviderView | null {
  const payload = toProviderViewPayload(value);
  const id = optionalText(payload.id);
  if (!id) {
    return null;
  }
  return {
    id,
    name: optionalText(payload.name),
    provider: optionalText(payload.provider),
    providerName: optionalText(payload.providerName),
    type: optionalText(payload.type),
    auth_type: optionalText(payload.auth_type),
    base_url: optionalText(payload.base_url),
    default_base_url: optionalText(payload.default_base_url),
    description: optionalText(payload.description),
    credential_id: optionalText(payload.credential_id),
    credential_effective_id: optionalText(payload.credential_effective_id),
    effective_credential_id: optionalText(payload.effective_credential_id),
    credential_label: optionalText(payload.credential_label),
    credential_preview: optionalText(payload.credential_preview),
    connected_count: optionalNumber(payload.connected_count),
    api_key_optional: optionalBoolean(payload.api_key_optional),
    requires_api_key: optionalBoolean(payload.requires_api_key),
    is_default: optionalBoolean(payload.is_default),
    preset_name: optionalText(payload.preset_name),
  };
}

function toProviderCredentialView(value: unknown): ProviderCredentialView | null {
  const payload = toProviderCredentialViewPayload(value);
  const id = optionalText(payload.id);
  if (!id) {
    return null;
  }
  return {
    id,
    label: optionalText(payload.label),
    name: optionalText(payload.name),
    secret_preview: optionalText(payload.secret_preview),
  };
}

function providerList(value: unknown): ProviderView[] {
  return Array.isArray(value)
    ? value.map(toProviderView).filter((provider): provider is ProviderView => provider !== null)
    : [];
}

function credentialList(value: unknown): ProviderCredentialView[] {
  return Array.isArray(value)
    ? value.map(toProviderCredentialView).filter((credential): credential is ProviderCredentialView => credential !== null)
    : [];
}

function toProviderCredentialEntries(value: unknown): ProviderCredentialEntry[] {
  const payload = toPayloadSource<ProviderCredentialMapPayload>(value);
  return payload ? Object.entries(payload) : [];
}

function normalizeProviderSettings(payload: unknown): ProviderSettings {
  const settings = toProviderSettingsPayload(payload);
  return {
    default_provider: optionalText(settings.default_provider) || "",
    connected: providerList(settings.connected),
    available: providerList(settings.available),
  };
}

function normalizeProviderCredentials(value: unknown): ProviderCredentialsState {
  return Object.fromEntries(
    toProviderCredentialEntries(value)
      .map(([providerKey, credentials]) => [providerKey, credentialList(credentials)] as const)
      .filter(([, credentials]) => credentials.length > 0),
  );
}

export async function loadProviderSettingsState(
  settingsState: ProviderSettingsLoaderState,
  requestSettingsJson: RequestSettingsJson,
  copy: { value: ProviderSettingsLoaderCopy },
): Promise<void> {
  settingsState.providersLoading = true;
  settingsState.providersError = "";
  try {
    const [providersPayload, credentialsPayload] = await Promise.all([
      requestSettingsJson("/api/settings/providers"),
      requestSettingsJson("/api/settings/credentials"),
    ]);
    const providers = normalizeProviderSettings(providersPayload);
    const credentials = toProviderCredentialsPayload(credentialsPayload);
    settingsState.providers = providers;
    settingsState.credentials = normalizeProviderCredentials(credentials.credentials);
  } catch (error: unknown) {
    settingsState.providersError = errorMessage(error) || copy.value.notices.providerLoadFailed;
  } finally {
    settingsState.providersLoading = false;
  }
}
