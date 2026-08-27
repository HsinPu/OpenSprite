import type { OpenRouterModel, ProviderId } from "../../api/providerConnections";
import { defaultTranslator, type Translator } from "../../i18n/catalog";

export type ModelCatalogItem = {
  id: string;
  label: string;
};

export type ModelSelection = {
  providerId: ProviderId;
  modelId: string;
};

export type ModelChoice = {
  selection: ModelSelection;
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

export function modelLabel(selection: ModelSelection | null, openRouterModels: ReadonlyArray<ModelCatalogItem> = [], t: Translator = defaultTranslator): string {
  if (!selection) return t("model.none");
  const catalog = selection.providerId === "openrouter" ? openRouterModels : localModelCatalog[selection.providerId];
  return catalog.find((model) => model.id === selection.modelId)?.label ?? selection.modelId;
}

export function openRouterModelCatalog(models: ReadonlyArray<OpenRouterModel>): ReadonlyArray<ModelCatalogItem> {
  return models.map((model) => ({ id: model.id, label: model.name }));
}
