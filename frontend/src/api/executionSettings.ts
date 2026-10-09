import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";
import { apiFetch } from "./http";

export type ExecutionSelection = { pluginId: string };
export type ExecutionPlugin = {
  id: string; name: string; description: string; version: string; apiVersion: number;
  status: "available" | "incompatible" | "unavailable";
};
export type ExecutionSettings = {
  selection: ExecutionSelection | null; revision: number;
  migration: { loopId: string; policyId: string } | null; plugins: ExecutionPlugin[];
};
export type ExecutionSettingsErrorCode = "invalid_request" | "plugin_unavailable" | "settings_store_unavailable"
  | "revision_conflict" | "migration_required" | "internal_error" | "malformed_response" | "network_error";

export class ExecutionSettingsApiError extends Error {
  constructor(readonly code: ExecutionSettingsErrorCode) { super(code); this.name = "ExecutionSettingsApiError"; }
}
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, keys: readonly string[]) => Object.keys(value).length === keys.length && Object.keys(value).every(key => keys.includes(key));
const pluginId = (value: unknown): value is string => typeof value === "string" && /^[a-z][a-z0-9_.-]{0,63}$/.test(value);
const text = (value: unknown, max: number, min = 0): value is string => typeof value === "string" && value.length >= min && value.length <= max;
const revision = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
const responseErrors = new Map<number, readonly ExecutionSettingsErrorCode[]>([
  [400, ["invalid_request"]], [409, ["revision_conflict", "migration_required"]],
  [503, ["plugin_unavailable", "settings_store_unavailable"]], [500, ["internal_error"]],
]);
function responseBody(value: unknown): ExecutionSettings {
  const invalid = () => new ExecutionSettingsApiError("malformed_response");
  if (!record(value) || !exactKeys(value, ["selection", "revision", "migration", "plugins"]) || !revision(value.revision)
    || !Array.isArray(value.plugins)) throw invalid();
  let selection: ExecutionSelection | null = null;
  let migration: ExecutionSettings["migration"] = null;
  if (value.selection !== null) {
    if (!record(value.selection) || !exactKeys(value.selection, ["pluginId"]) || !pluginId(value.selection.pluginId)) throw invalid();
    selection = { pluginId: value.selection.pluginId };
  }
  if (value.migration !== null) {
    if (!record(value.migration) || !exactKeys(value.migration, ["loopId", "policyId"])
      || !pluginId(value.migration.loopId) || !pluginId(value.migration.policyId)) throw invalid();
    migration = { loopId: value.migration.loopId, policyId: value.migration.policyId };
  }
  if ((selection === null) !== (migration !== null) || (migration && value.revision !== 0)) throw invalid();
  const identities = new Set<string>();
  const plugins = value.plugins.map((item: unknown): ExecutionPlugin => {
    if (!record(item) || !exactKeys(item, ["id", "name", "description", "version", "apiVersion", "status"])
      || !pluginId(item.id) || !text(item.name, 128, 1) || !text(item.description, 2048) || !text(item.version, 64, 1)
      || typeof item.apiVersion !== "number" || !Number.isSafeInteger(item.apiVersion) || item.apiVersion < 1
      || !["available", "incompatible", "unavailable"].includes(String(item.status)) || identities.has(item.id)
      || (item.status === "available" && item.apiVersion !== 4)) throw invalid();
    identities.add(item.id);
    return { id: item.id, name: item.name, description: item.description, version: item.version,
      apiVersion: item.apiVersion, status: item.status as ExecutionPlugin["status"] };
  });
  return { selection, revision: value.revision, migration, plugins };
}
async function request(selection?: ExecutionSelection, expectedRevision?: number): Promise<ExecutionSettings> {
  let response: Response;
  try {
    response = await apiFetch("/api/settings/execution", selection ? {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pluginId: selection.pluginId, expectedRevision }),
    } : undefined);
  } catch { throw new ExecutionSettingsApiError("network_error"); }
  let body: unknown;
  try { body = await response.json(); } catch { throw new ExecutionSettingsApiError("malformed_response"); }
  if (response.status !== 200) {
    if (response.ok || !record(body) || !exactKeys(body, ["error"]) || !record(body.error)
      || !exactKeys(body.error, ["code", "message", "retryable"]) || typeof body.error.code !== "string"
      || !responseErrors.get(response.status)?.includes(body.error.code as ExecutionSettingsErrorCode)
      || (!selection && [400, 409].includes(response.status))
      || typeof body.error.message !== "string" || typeof body.error.retryable !== "boolean") {
      throw new ExecutionSettingsApiError("malformed_response");
    }
    throw new ExecutionSettingsApiError(body.error.code as ExecutionSettingsErrorCode);
  }
  const result = responseBody(body);
  if (selection && (result.selection?.pluginId !== selection.pluginId || result.migration !== null
    || result.revision !== expectedRevision! + 1)) throw new ExecutionSettingsApiError("malformed_response");
  return result;
}
const pendingWrites = new Set<Promise<ExecutionSettings>>();
export async function getExecutionSettings(): Promise<ExecutionSettings> {
  while (pendingWrites.size > 0) await Promise.allSettled([...pendingWrites]);
  return request();
}
export function putExecutionSettings(selection: ExecutionSelection, expectedRevision: number): Promise<ExecutionSettings> {
  if (!pluginId(selection.pluginId) || !revision(expectedRevision) || expectedRevision === Number.MAX_SAFE_INTEGER)
    return Promise.reject(new ExecutionSettingsApiError("invalid_request"));
  const write = request(selection, expectedRevision);
  pendingWrites.add(write);
  void write.then(() => pendingWrites.delete(write), () => pendingWrites.delete(write));
  return write;
}
export function executionSettingsErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof ExecutionSettingsApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "execution.error.invalidRequest", plugin_unavailable: "execution.error.pluginUnavailable",
    settings_store_unavailable: "execution.error.storeUnavailable", revision_conflict: "execution.error.revisionConflict",
    migration_required: "execution.migrationRequired", internal_error: "execution.error.internal",
    malformed_response: "execution.error.malformed", network_error: "error.network",
  } satisfies Record<ExecutionSettingsErrorCode, MessageKey>;
  return t(keys[code]);
}
