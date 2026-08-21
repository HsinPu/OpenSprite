import { providerIds, type ProviderId } from "./providerConnections";

export type PersistedModelSelection = {
  providerId: ProviderId;
  modelId: string;
};

export type ResponseMode = "default" | "fast" | "balanced" | "deep";

export type AiSettings = {
  model: PersistedModelSelection | null;
  responseMode: ResponseMode;
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

function model(value: unknown): PersistedModelSelection | null {
  if (value === null) return null;
  if (!record(value) || !exactKeys(value, ["providerId", "modelId"]) || !providerIds.includes(value.providerId as ProviderId) || typeof value.modelId !== "string" || codePointLength(value.modelId) < 1 || codePointLength(value.modelId) > 256 || !value.modelId.trim()) {
    throw new AiSettingsApiError("malformed_response");
  }
  return { providerId: value.providerId as ProviderId, modelId: value.modelId };
}

function responseBody(value: unknown): AiSettings {
  if (!record(value) || !exactKeys(value, ["model", "responseMode"]) || typeof value.responseMode !== "string" || !responseModes.includes(value.responseMode as ResponseMode)) {
    throw new AiSettingsApiError("malformed_response");
  }
  return { model: model(value.model), responseMode: value.responseMode as ResponseMode };
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
    response = await fetch("/api/settings/ai", init);
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
  return request({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(next) }, new Map([[400, ["invalid_request"]], [409, ["not_connected"]], [503, ["credential_store_unavailable", "settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function aiSettingsErrorText(error: unknown): string {
  const code = error instanceof AiSettingsApiError ? error.code : "network_error";
  return ({
    invalid_request: "AI 設定資料無效，請重新選擇。",
    not_connected: "這個模型廠家目前尚未連線。",
    credential_store_unavailable: "安全憑證儲存服務暫時無法使用。",
    settings_store_unavailable: "AI 設定暫時無法讀取或儲存。",
    internal_error: "本機服務暫時無法儲存 AI 設定，請稍後再試。",
    malformed_response: "本機服務回傳的 AI 設定無法安全使用，請重試。",
    network_error: "無法連線到本機服務，請確認 OpenSprite 正在執行。",
  } satisfies Record<AiSettingsErrorCode, string>)[code];
}
