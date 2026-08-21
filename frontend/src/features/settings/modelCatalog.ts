import type { OpenRouterModel, ProviderId } from "../../api/providerConnections";

export type ModelCatalogItem = {
  id: string;
  label: string;
};

export type ModelSelection = {
  providerId: ProviderId;
  modelId: string;
  label: string;
};

export const localModelCatalog: Record<ProviderId, ReadonlyArray<ModelCatalogItem>> = {
  openai: [
    { id: "gpt-5.6", label: "GPT-5.6" },
    { id: "gpt-5.6-mini", label: "GPT-5.6 mini" },
  ],
  anthropic: [
    { id: "claude-sonnet-4", label: "Claude Sonnet 4" },
    { id: "claude-haiku-4", label: "Claude Haiku 4" },
  ],
  openrouter: [],
};

export function modelLabel(selection: ModelSelection): string {
  return selection.label || selection.modelId;
}

export function openRouterModelCatalog(models: ReadonlyArray<OpenRouterModel>): ReadonlyArray<ModelCatalogItem> {
  return models.map((model) => ({ id: model.id, label: model.name }));
}
