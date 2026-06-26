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

export function mediaModelCategories(copy: AnyRecord) {
  const categories = copy.settings.models?.mediaCategories || {};
  return [
    { key: "vision", mark: "VI", title: categories.vision?.title || "Vision", description: categories.vision?.description || "" },
    { key: "ocr", mark: "OC", title: categories.ocr?.title || "OCR", description: categories.ocr?.description || "" },
    { key: "speech", mark: "SP", title: categories.speech?.title || "Speech", description: categories.speech?.description || "" },
    { key: "video", mark: "VD", title: categories.video?.title || "Video", description: categories.video?.description || "" },
  ];
}

export function mediaModelsForProvider(state: AnyRecord, category: string, providerId: string, selectedModel = "") {
  const provider = (state.media.providers || []).find((entry: AnyRecord) => entry.id === providerId);
  const mediaModels = provider?.media_models?.[category];
  const models = Array.isArray(mediaModels) ? [...mediaModels] : Array.isArray(provider?.models) ? [...provider.models] : [];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}
