import type { AnyRecord } from "./providerHelpers";

export function modelOptionsForProvider(provider: AnyRecord, selectedModel = "") {
  const models = Array.isArray(provider?.models) ? [...provider.models] : [];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}

function formatCompactTokenCount(value: any) {
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

export function textModelOptionLabel(copy: AnyRecord, provider: AnyRecord, model: string) {
  const contextLength = provider?.model_metadata?.[model]?.context_length;
  const formatted = formatCompactTokenCount(contextLength);
  const context = formatted && typeof copy.settings.models?.modelMetadata?.contextLength === "function"
    ? copy.settings.models.modelMetadata.contextLength(formatted)
    : "";
  const label = [model, context].filter(Boolean).join(" - ");
  return provider?.is_default && provider.selected_model === model
    ? `${label} (${copy.settings.models?.active || "active"})`
    : label;
}
