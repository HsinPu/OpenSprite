export type ProviderPayload = {
  id?: unknown;
  name?: unknown;
  providerName?: unknown;
  connected_count?: unknown;
  default_base_url?: unknown;
  base_url?: unknown;
  credential_id?: unknown;
  provider?: unknown;
};

export type ProviderOAuthConnectOptions = {
  providerName?: string;
};

export interface ProviderConnectForm {
  providerId: string;
  name: string;
  apiKey: string;
  baseUrl: string;
  showAdvanced: boolean;
}

export type ProviderConnectPayload = {
  name: string;
  api_key: string;
  base_url: string;
};

export type ProviderOAuthConnectPayload = {
  name: string;
  base_url: string;
};

export type ProviderCredentialPayload = {
  credential_id: string;
};

export function createEmptyProviderConnectForm(): ProviderConnectForm {
  return {
    providerId: "",
    name: "",
    apiKey: "",
    baseUrl: "",
    showAdvanced: false,
  };
}

function optionalText(value: unknown): string {
  return String(value || "").trim();
}

export function createProviderConnectForm(provider: ProviderPayload): ProviderConnectForm {
  const name = optionalText(provider.name);
  const connectedCount = Number(provider.connected_count || 0);
  return {
    ...createEmptyProviderConnectForm(),
    providerId: optionalText(provider.id),
    name: connectedCount ? `${name} ${connectedCount + 1}` : name,
    baseUrl: optionalText(provider.default_base_url || provider.base_url),
  };
}

export function resetProviderConnectForm(form: ProviderConnectForm): void {
  Object.assign(form, createEmptyProviderConnectForm());
}

export function providerConnectPayloadFromForm(form: ProviderConnectForm): ProviderConnectPayload {
  return {
    name: form.name,
    api_key: form.apiKey,
    base_url: form.baseUrl,
  };
}

export function providerOAuthConnectPayload(
  provider: ProviderPayload | null | undefined,
  options: ProviderOAuthConnectOptions,
): ProviderOAuthConnectPayload {
  return {
    name: optionalText(provider?.name || options.providerName),
    base_url: optionalText(provider?.default_base_url),
  };
}

export function providerCredentialPayload(credentialId: string): ProviderCredentialPayload {
  return { credential_id: credentialId };
}
