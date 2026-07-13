export type ProviderLike = {
  id?: unknown;
  provider?: unknown;
  providerName?: unknown;
  name?: unknown;
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

export type ProviderMarkSource = Pick<ProviderLike, "id" | "name" | "type">;

type ProviderCollection = {
  available?: unknown;
  connected?: unknown;
};

type ProviderSettingsState = {
  providers?: ProviderCollection;
};

function providerList(value: unknown): ProviderLike[] {
  return Array.isArray(value)
    ? value.filter((item): item is ProviderLike => item !== null && typeof item === "object" && !Array.isArray(item))
    : [];
}

export function providerCatalogKey(provider: ProviderLike | null | undefined): string {
  return String(provider?.provider || provider?.id || "").trim();
}

export function providerMark(value: ProviderMarkSource | null | undefined): string {
  return String(value?.name || value?.id || value?.type || "??").trim().slice(0, 2).toUpperCase();
}

export function hasConnectedProvider(state: ProviderSettingsState, presetId: string): boolean {
  return providerList(state.providers?.connected).some((provider) => providerCatalogKey(provider) === presetId);
}

export function selectedConnectProvider(providers: ProviderCollection, providerId: string): ProviderLike | null {
  return [...providerList(providers.available), ...providerList(providers.connected)]
    .find((provider) => String(provider.id || "") === providerId) || null;
}
