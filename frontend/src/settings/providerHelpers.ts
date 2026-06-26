export type AnyRecord = Record<string, any>;

export function providerCatalogKey(provider: AnyRecord) {
  return provider?.provider || provider?.id;
}

export function providerMark(value: AnyRecord) {
  return String(value?.name || value?.id || value?.type || "??").trim().slice(0, 2).toUpperCase();
}

export function hasConnectedProvider(state: AnyRecord, presetId: string) {
  return (state.providers?.connected || []).some((provider: AnyRecord) => providerCatalogKey(provider) === presetId);
}

export function selectedConnectProvider(providers: AnyRecord, providerId: string) {
  return [...(providers.available || []), ...(providers.connected || [])]
    .find((provider: AnyRecord) => provider.id === providerId) || null;
}
