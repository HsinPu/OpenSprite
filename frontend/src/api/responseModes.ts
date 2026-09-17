import { apiFetch } from "./http";
import type { ProviderId } from "./providerConnections";

export const responseModes = ["default", "low", "medium", "high", "xhigh", "max", "ultra"] as const;
export type ResponseMode = typeof responseModes[number];
export const historicalResponseModes = ["fast", "balanced", "deep", ...responseModes] as const;
export type HistoricalResponseMode = typeof historicalResponseModes[number];
export const nativeEfforts = ["none", "minimal", "low", "medium", "high", "xhigh", "max"] as const;
export type ReasoningResolution = {
  requested: HistoricalResponseMode;
  effective: typeof nativeEfforts[number] | null;
  status: "exact" | "fallback" | "provider_default" | "unknown";
};

export function isReasoningResolution(value: unknown): value is ReasoningResolution {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  if (Object.keys(item).length !== 3 || !historicalResponseModes.includes(item.requested as HistoricalResponseMode)) return false;
  if (item.status === "exact" || item.status === "fallback") return nativeEfforts.includes(item.effective as typeof nativeEfforts[number]);
  return (item.status === "provider_default" || item.status === "unknown") && item.effective === null;
}

export async function getResponseModeResolution(providerId: ProviderId, modelId: string, responseMode: ResponseMode, signal: AbortSignal): Promise<ReasoningResolution> {
  const query = new URLSearchParams({ providerId, modelId, responseMode });
  const response = await apiFetch(`/api/settings/ai/response-mode?${query}`, { signal });
  if (!response.ok) throw new Error("response_mode_unavailable");
  const value: unknown = await response.json();
  if (!isReasoningResolution(value) || value.requested !== responseMode) throw new Error("invalid_response_mode_resolution");
  return value;
}
