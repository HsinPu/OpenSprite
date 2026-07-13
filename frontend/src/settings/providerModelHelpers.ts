import { toPayloadSource } from "../composables/payloadBoundary";
import type { ModelProviderView as SettingsModelProviderView } from "../composables/useSettingsState";

type ModelProviderView = Pick<SettingsModelProviderView, "is_default" | "model_metadata" | "models" | "selected_model">;
type ModelCopyRootPayload = {
  settings?: unknown;
};
type ModelCopySettingsPayload = {
  models?: unknown;
};
type ModelCopyView = {
  active?: unknown;
  modelMetadata?: unknown;
};
type ModelMetadataCopyView = {
  contextLength?: unknown;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

export function modelOptionsForProvider(provider: ModelProviderView | null | undefined, selectedModel = ""): string[] {
  const models = [...(provider?.models ?? [])];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}

function formatCompactTokenCount(value: unknown): string {
  const tokens = Number(value);
  if (!Number.isFinite(tokens) || tokens <= 0) {
    return "";
  }
  if (tokens >= 1_000_000) {
    const millions = tokens / 1_000_000;
    return `${Number(millions.toFixed(millions >= 10 ? 0 : 1))}M`;
  }
  if (tokens >= 1_000) {
    return `${Math.round(tokens / 1_000)}K`;
  }
  return String(Math.round(tokens));
}

export function textModelOptionLabel(copy: unknown, provider: ModelProviderView | null | undefined, model: string): string {
  const modelMetadataEntry = provider?.model_metadata?.[model] ?? {};
  const root = toPayloadSource<ModelCopyRootPayload>(copy);
  const settings = toPayloadSource<ModelCopySettingsPayload>(root?.settings);
  const modelsCopy = toPayloadSource<ModelCopyView>(settings?.models) || {};
  const modelMetadataCopy = toPayloadSource<ModelMetadataCopyView>(modelsCopy.modelMetadata) || {};
  const contextLength = modelMetadataEntry.context_length;
  const formatted = formatCompactTokenCount(contextLength);
  const context = formatted && typeof modelMetadataCopy.contextLength === "function"
    ? String(modelMetadataCopy.contextLength(formatted))
    : "";
  const label = [model, context].filter(Boolean).join(" - ");
  return provider?.is_default && provider.selected_model === model
    ? `${label} (${text(modelsCopy.active, "active")})`
    : label;
}
