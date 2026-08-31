import type { OpenRouterModel, ProviderId } from "../../api/providerConnections";
import type { PersistedModelSelection } from "../../api/aiSettings";
import { defaultTranslator, type Translator } from "../../i18n/catalog";

export type ModelCatalogItem = {
  id: string;
  label: string;
  contextWindowTokens: number;
  maxOutputTokens: number;
};

export type ModelSelection = PersistedModelSelection;

export type ModelChoice = {
  selection: ModelSelection;
  label: string;
  contextWindowTokens?: number;
  maxOutputTokens?: number;
};

export const localModelCatalog: Record<ProviderId, ReadonlyArray<ModelCatalogItem>> = {
  openai: [
    { id: "gpt-5.6", label: "GPT-5.6", contextWindowTokens: 1_050_000, maxOutputTokens: 128_000 },
    { id: "gpt-5.6-luna", label: "GPT-5.6 Luna", contextWindowTokens: 1_050_000, maxOutputTokens: 128_000 },
  ],
  anthropic: [
    { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", contextWindowTokens: 1_000_000, maxOutputTokens: 128_000 },
    { id: "claude-haiku-4-5", label: "Claude Haiku 4.5", contextWindowTokens: 200_000, maxOutputTokens: 64_000 },
  ],
  openrouter: [],
};

export function modelLabel(selection: ModelSelection | null, openRouterModels: ReadonlyArray<Pick<ModelCatalogItem, "id" | "label">> = [], t: Translator = defaultTranslator): string {
  if (!selection) return t("model.none");
  const catalog = selection.providerId === "openrouter" ? openRouterModels : localModelCatalog[selection.providerId];
  return catalog.find((model) => model.id === selection.modelId)?.label ?? selection.modelId;
}

export function openRouterModelCatalog(models: ReadonlyArray<OpenRouterModel>): ReadonlyArray<ModelCatalogItem> {
  return models.map((model) => ({ id: model.id, label: model.name, contextWindowTokens: model.contextWindowTokens, maxOutputTokens: model.maxOutputTokens ?? Math.min(32_768, model.contextWindowTokens) }));
}
