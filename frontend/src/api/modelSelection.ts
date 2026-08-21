import { providerIds, type ProviderId } from "./providerConnections";

export type PersistedModelSelection = {
  providerId: ProviderId;
  modelId: string;
};

export type ModelSelectionErrorCode = "invalid_request" | "not_connected" | "credential_store_unavailable" | "settings_store_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class ModelSelectionApiError extends Error {
  constructor(readonly code: ModelSelectionErrorCode) {
    super(code);
    this.name = "ModelSelectionApiError";
  }
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const codePointLength = (value: string) => Array.from(value).length;
const errorCodes = ["invalid_request", "not_connected", "credential_store_unavailable", "settings_store_unavailable", "internal_error"] as const;

function selection(value: unknown): PersistedModelSelection | null {
  if (value === null) return null;
  if (!record(value) || !exactKeys(value, ["providerId", "modelId"]) || !providerIds.includes(value.providerId as ProviderId) || typeof value.modelId !== "string" || codePointLength(value.modelId) < 1 || codePointLength(value.modelId) > 256 || !value.modelId.trim()) {
    throw new ModelSelectionApiError("malformed_response");
  }
  return { providerId: value.providerId as ProviderId, modelId: value.modelId };
}

function responseBody(value: unknown): PersistedModelSelection | null {
  if (!record(value) || !exactKeys(value, ["selection"])) throw new ModelSelectionApiError("malformed_response");
  return selection(value.selection);
}

function errorCode(value: unknown, allowed: readonly string[]): ModelSelectionErrorCode {
  if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error) || !exactKeys(value.error, ["code", "message", "retryable"]) || typeof value.error.code !== "string" || !errorCodes.includes(value.error.code as (typeof errorCodes)[number]) || !allowed.includes(value.error.code) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") {
    throw new ModelSelectionApiError("malformed_response");
  }
  return value.error.code as ModelSelectionErrorCode;
}

async function request(init: RequestInit | undefined, errors: ReadonlyMap<number, readonly string[]>): Promise<PersistedModelSelection | null> {
  let response: Response;
  try {
    response = await fetch("/api/settings/model", init);
  } catch {
    throw new ModelSelectionApiError("network_error");
  }
  if (response.status !== 200) {
    if (response.ok) throw new ModelSelectionApiError("malformed_response");
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new ModelSelectionApiError("malformed_response");
    }
    throw new ModelSelectionApiError(errorCode(body, errors.get(response.status) ?? []));
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ModelSelectionApiError("malformed_response");
  }
  return responseBody(body);
}

export function getModelSelection(): Promise<PersistedModelSelection | null> {
  return request(undefined, new Map([[503, ["settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function putModelSelection(next: PersistedModelSelection | null): Promise<PersistedModelSelection | null> {
  return request({ method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ selection: next }) }, new Map([[400, ["invalid_request"]], [409, ["not_connected"]], [503, ["credential_store_unavailable", "settings_store_unavailable"]], [500, ["internal_error"]]]));
}

export function modelSelectionErrorText(error: unknown): string {
  const code = error instanceof ModelSelectionApiError ? error.code : "network_error";
  return ({
    invalid_request: "模型選擇資料無效，請重新選擇。",
    not_connected: "這個模型廠家目前尚未連線。",
    credential_store_unavailable: "安全憑證儲存服務暫時無法使用。",
    settings_store_unavailable: "模型設定暫時無法讀取或儲存。",
    internal_error: "本機服務暫時無法儲存模型設定，請稍後再試。",
    malformed_response: "本機服務回傳的模型設定無法安全使用，請重試。",
    network_error: "無法連線到本機服務，請確認 OpenSprite 正在執行。",
  } satisfies Record<ModelSelectionErrorCode, string>)[code];
}
