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
