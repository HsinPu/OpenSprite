import { isProviderId, type ProviderId } from "./providerConnections";
import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";

export type PersistedModelSelection = {
  providerId: ProviderId;
  modelId: string;
  contextBudget: ContextBudget;
  outputBudget: OutputBudget;
};

export type ResponseMode = "default" | "fast" | "balanced" | "deep";
export type ContextBudget = "auto" | "32k" | "64k" | "128k" | "256k" | "max";
export type OutputBudget = "auto" | "8k" | "16k" | "32k" | "64k" | "max";
export type OutputContinuation = "off" | "1" | "2" | "3" | "5" | "10" | "20" | "50" | "unlimited";
export type ResponseDelivery = "stream" | "complete";
export type NativeProviderId = "openai" | "anthropic" | "openrouter";
export type ProviderToolPolicy = { toolsEnabled: boolean; transport: "stream" | "non_streaming"; disabledModels: string[] };

export type AiSettings = {
  model: PersistedModelSelection | null;
  responseMode: ResponseMode;
  outputContinuation: OutputContinuation;
  responseDelivery: ResponseDelivery;
  logFullPrompts: boolean;
  providerToolPolicies?: Partial<Record<NativeProviderId, ProviderToolPolicy>>;
};

export type AiSettingsErrorCode = "invalid_request" | "not_connected" | "credential_store_unavailable" | "settings_store_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class AiSettingsApiError extends Error {
  constructor(readonly code: AiSettingsErrorCode) {
    super(code);
    this.name = "AiSettingsApiError";
  }
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const codePointLength = (value: string) => Array.from(value).length;
const errorCodes = ["invalid_request", "not_connected", "credential_store_unavailable", "settings_store_unavailable", "internal_error"] as const;
const responseModes = ["default", "fast", "balanced", "deep"] as const;
const contextBudgets = ["auto", "32k", "64k", "128k", "256k", "max"] as const;
const outputBudgets = ["auto", "8k", "16k", "32k", "64k", "max"] as const;
const outputContinuations = ["off", "1", "2", "3", "5", "10", "20", "50", "unlimited"] as const;
const responseDeliveries = ["stream", "complete"] as const;

function model(value: unknown): PersistedModelSelection | null {
  if (value === null) return null;
  if (!record(value) || !exactKeys(value, ["providerId", "modelId", "contextBudget", "outputBudget"]) || !isProviderId(value.providerId) || typeof value.modelId !== "string" || codePointLength(value.modelId) < 1 || codePointLength(value.modelId) > 256 || !value.modelId.trim() || typeof value.contextBudget !== "string" || !contextBudgets.includes(value.contextBudget as ContextBudget) || typeof value.outputBudget !== "string" || !outputBudgets.includes(value.outputBudget as OutputBudget)) {
    throw new AiSettingsApiError("malformed_response");
  }
  return { providerId: value.providerId as ProviderId, modelId: value.modelId, contextBudget: value.contextBudget as ContextBudget, outputBudget: value.outputBudget as OutputBudget };
}

function responseBody(value: unknown): AiSettings {
  if (!record(value) || !exactKeys(value, ["model", "responseMode", "outputContinuation", "responseDelivery", "logFullPrompts", ...("providerToolPolicies" in value ? ["providerToolPolicies"] : [])]) || typeof value.responseMode !== "string" || !responseModes.includes(value.responseMode as ResponseMode) || typeof value.outputContinuation !== "string" || !outputContinuations.includes(value.outputContinuation as OutputContinuation) || typeof value.responseDelivery !== "string" || !responseDeliveries.includes(value.responseDelivery as ResponseDelivery) || typeof value.logFullPrompts !== "boolean") {
    throw new AiSettingsApiError("malformed_response");
  }
  if ("providerToolPolicies" in value && (!record(value.providerToolPolicies) || Object.entries(value.providerToolPolicies).some(([key, policy]) => !["openai", "anthropic", "openrouter"].includes(key) || !record(policy) || !exactKeys(policy, ["toolsEnabled", "transport", "disabledModels"]) || typeof policy.toolsEnabled !== "boolean" || !["stream", "non_streaming"].includes(String(policy.transport)) || !Array.isArray(policy.disabledModels) || policy.disabledModels.some(id => typeof id !== "string")))) throw new AiSettingsApiError("malformed_response");
  return { model: model(value.model), responseMode: value.responseMode as ResponseMode, outputContinuation: value.outputContinuation as OutputContinuation, responseDelivery: value.responseDelivery as ResponseDelivery, logFullPrompts: value.logFullPrompts, ...("providerToolPolicies" in value ? { providerToolPolicies: value.providerToolPolicies as AiSettings["providerToolPolicies"] } : {}) };
}

function errorCode(value: unknown, allowed: readonly string[]): AiSettingsErrorCode {
  if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error) || !exactKeys(value.error, ["code", "message", "retryable"]) || typeof value.error.code !== "string" || !errorCodes.includes(value.error.code as (typeof errorCodes)[number]) || !allowed.includes(value.error.code) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") {
    throw new AiSettingsApiError("malformed_response");
  }
  return value.error.code as AiSettingsErrorCode;
}

async function request(init: RequestInit | undefined, errors: ReadonlyMap<number, readonly string[]>): Promise<AiSettings> {
  let response: Response;
  try {
    response = await apiFetch("/api/settings/ai", init);
  } catch {
    throw new AiSettingsApiError("network_error");
  }
  if (response.status !== 200) {
    if (response.ok) throw new AiSettingsApiError("malformed_response");
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new AiSettingsApiError("malformed_response");
    }
    throw new AiSettingsApiError(errorCode(body, errors.get(response.status) ?? []));
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new AiSettingsApiError("malformed_response");
  }
  return responseBody(body);
}

export function getAiSettings(): Promise<AiSettings> {
  return request(undefined, new Map([[503, ["settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function putAiSettings(next: AiSettings): Promise<AiSettings> {
  const { providerToolPolicies: _policies, ...preferences } = next;
  return request({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(preferences) }, new Map([[400, ["invalid_request"]], [409, ["not_connected"]], [503, ["credential_store_unavailable", "settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export async function putProviderToolPolicy(provider: NativeProviderId, policy: ProviderToolPolicy): Promise<AiSettings> {
  const response = await apiFetch(`/api/settings/ai/providers/${provider}/tools`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(policy) });
  if (!response.ok) throw new AiSettingsApiError("settings_store_unavailable");
  return responseBody(await response.json());
}

export function aiSettingsErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof AiSettingsApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "error.ai.invalidRequest",
    not_connected: "error.ai.notConnected",
    credential_store_unavailable: "error.ai.credentialStore",
    settings_store_unavailable: "error.ai.settingsStore",
    internal_error: "error.ai.internal",
    malformed_response: "error.ai.malformed",
    network_error: "error.network",
  } satisfies Record<AiSettingsErrorCode, MessageKey>;
  return t(keys[code]);
}
import { apiFetch } from "./http";
