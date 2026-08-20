import type { ProviderId } from "../../api/providerConnections";

export type ModelSelection = {
  providerId: ProviderId;
  modelId: string;
};

export const localModelCatalog: Record<ProviderId, ReadonlyArray<{ id: string; label: string }>> = {
  openai: [
    { id: "gpt-5.6", label: "GPT-5.6" },
    { id: "gpt-5.6-mini", label: "GPT-5.6 mini" },
  ],
  anthropic: [
    { id: "claude-sonnet-4", label: "Claude Sonnet 4" },
    { id: "claude-haiku-4", label: "Claude Haiku 4" },
  ],
};

export function modelLabel(selection: ModelSelection): string {
  return localModelCatalog[selection.providerId].find((model) => model.id === selection.modelId)?.label ?? selection.modelId;
}
