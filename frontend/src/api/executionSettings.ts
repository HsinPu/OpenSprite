import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";
import { apiFetch } from "./http";

export type ExecutionSelection = { loopId: string; policyId: string };
export type ExecutionPlugin = {
  id: string;
  kind: "loop" | "policy";
  name: string;
  description: string;
  version: string;
  apiVersion: number;
  status: "available" | "incompatible" | "unavailable";
};
export type ExecutionSettings = { selection: ExecutionSelection; plugins: ExecutionPlugin[] };
export type ExecutionSettingsErrorCode = "invalid_request" | "plugin_unavailable" | "settings_store_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class ExecutionSettingsApiError extends Error {
  constructor(readonly code: ExecutionSettingsErrorCode) {
    super(code);
    this.name = "ExecutionSettingsApiError";
  }
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, keys: readonly string[]) => Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));
const pluginId = (value: unknown): value is string => typeof value === "string" && /^[a-z][a-z0-9_.-]{0,63}$/.test(value);
const text = (value: unknown, max: number, min = 0): value is string => typeof value === "string" && value.length >= min && value.length <= max;
const serverCodes = ["invalid_request", "plugin_unavailable", "settings_store_unavailable", "internal_error"] as const;
const responseErrors = new Map([[400, ["invalid_request"]], [503, ["plugin_unavailable", "settings_store_unavailable"]], [500, ["internal_error"]]]);

function responseBody(value: unknown): ExecutionSettings {
  if (!record(value) || !exactKeys(value, ["selection", "plugins"])
    || !record(value.selection) || !exactKeys(value.selection, ["loopId", "policyId"])
    || !pluginId(value.selection.loopId) || !pluginId(value.selection.policyId) || !Array.isArray(value.plugins)) {
    throw new ExecutionSettingsApiError("malformed_response");
  }
  const identities = new Set<string>();
  const plugins: ExecutionPlugin[] = value.plugins.map((item: unknown) => {
    if (!record(item) || !exactKeys(item, ["id", "kind", "name", "description", "version", "apiVersion", "status"])
      || !pluginId(item.id) || (item.kind !== "loop" && item.kind !== "policy")
      || !text(item.name, 128, 1) || !text(item.description, 2048) || !text(item.version, 128, 1)
      || typeof item.apiVersion !== "number" || !Number.isSafeInteger(item.apiVersion) || item.apiVersion < 1
      || (item.status !== "available" && item.status !== "incompatible" && item.status !== "unavailable")) {
      throw new ExecutionSettingsApiError("malformed_response");
    }
    const identity = `${item.kind}:${item.id}`;
    if (identities.has(identity)) throw new ExecutionSettingsApiError("malformed_response");
    identities.add(identity);
    return { id: item.id, kind: item.kind, name: item.name, description: item.description, version: item.version, apiVersion: item.apiVersion, status: item.status };
  });
  // A removed plugin can remain selected in persisted settings. Keep its ID visible
  // so the user can choose an available replacement without silently changing it.
  return { selection: { loopId: value.selection.loopId, policyId: value.selection.policyId }, plugins };
}

function errorCode(value: unknown, status: number, writing: boolean): ExecutionSettingsErrorCode {
  const allowed = status === 400 && !writing ? [] : responseErrors.get(status) ?? [];
  if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error)
    || !exactKeys(value.error, ["code", "message", "retryable"])
    || typeof value.error.code !== "string" || !serverCodes.includes(value.error.code as typeof serverCodes[number])
    || !allowed.includes(value.error.code) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") {
    throw new ExecutionSettingsApiError("malformed_response");
  }
  return value.error.code as ExecutionSettingsErrorCode;
}

async function request(selection?: ExecutionSelection): Promise<ExecutionSettings> {
  let response: Response;
  try {
    response = await apiFetch("/api/settings/execution", selection ? {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ loopId: selection.loopId, policyId: selection.policyId }),
    } : undefined);
  } catch {
    throw new ExecutionSettingsApiError("network_error");
  }
  let body: unknown;
  try { body = await response.json(); } catch { throw new ExecutionSettingsApiError("malformed_response"); }
  if (response.status !== 200) {
    if (response.ok) throw new ExecutionSettingsApiError("malformed_response");
    throw new ExecutionSettingsApiError(errorCode(body, response.status, selection !== undefined));
  }
  const result = responseBody(body);
  if (selection && (result.selection.loopId !== selection.loopId || result.selection.policyId !== selection.policyId)) {
    throw new ExecutionSettingsApiError("malformed_response");
  }
  return result;
}

const pendingWrites = new Set<Promise<ExecutionSettings>>();

export async function getExecutionSettings(): Promise<ExecutionSettings> {
  // Settings can unmount while saving. A new page must read after every in-flight
  // write settles, including failed writes, rather than display an earlier value.
  while (pendingWrites.size > 0) await Promise.allSettled([...pendingWrites]);
  return request();
}

export function putExecutionSettings(selection: ExecutionSelection): Promise<ExecutionSettings> {
  const write = request(selection);
  pendingWrites.add(write);
  void write.then(() => pendingWrites.delete(write), () => pendingWrites.delete(write));
  return write;
}

export function executionSettingsErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof ExecutionSettingsApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "execution.error.invalidRequest",
    plugin_unavailable: "execution.error.pluginUnavailable",
    settings_store_unavailable: "execution.error.storeUnavailable",
    internal_error: "execution.error.internal",
    malformed_response: "execution.error.malformed",
    network_error: "error.network",
  } satisfies Record<ExecutionSettingsErrorCode, MessageKey>;
  return t(keys[code]);
}
