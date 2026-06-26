export function createEmptyProviderConnectForm() {
  return {
    providerId: "",
    name: "",
    apiKey: "",
    baseUrl: "",
    showAdvanced: false,
  };
}

export function createProviderConnectForm(provider) {
  return {
    ...createEmptyProviderConnectForm(),
    providerId: provider.id,
    name: provider.connected_count ? `${provider.name} ${provider.connected_count + 1}` : provider.name,
    baseUrl: provider.default_base_url || provider.base_url || "",
  };
}

export function providerConnectPayloadFromForm(form) {
  return {
    name: form.name,
    api_key: form.apiKey,
    base_url: form.baseUrl,
  };
}

export function providerOAuthConnectPayload(provider, options) {
  return {
    name: provider?.name || options.providerName,
    base_url: provider?.default_base_url || "",
  };
}

export function providerCredentialPayload(credentialId) {
  return { credential_id: credentialId };
}

export function providerCredentialKey(provider) {
  return provider?.provider || provider?.id;
}
