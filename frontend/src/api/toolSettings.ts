import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";


export const toolSources = ["builtin", "mcp", "external"] as const;
export const toolEffects = ["read_only", "local_write", "external_write", "destructive", "sensitive"] as const;
export type ToolSource = typeof toolSources[number];
export type ToolEffect = typeof toolEffects[number];

export type ToolSummary = {
  id: string;
  source: ToolSource;
  effect: ToolEffect;
  available: boolean;
};

export type ToolCatalog = { items: ToolSummary[] };
export type ToolSettings = { enabled: boolean; enabledTools: string[] };
export type ToolSettingsErrorCode = "invalid_request" | "tool_not_found" | "settings_store_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class ToolSettingsApiError extends Error {
  constructor(readonly code: ToolSettingsErrorCode) {
    super(code);
    this.name = "ToolSettingsApiError";
  }
}

const toolId = /^[a-z][a-z0-9_]{0,63}$/;
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const serverCodes = ["invalid_request", "tool_not_found", "settings_store_unavailable", "internal_error"] as const;

function settingsBody(value: unknown): ToolSettings {
  if (!record(value)
    || !exactKeys(value, ["enabled", "enabledTools"])
    || typeof value.enabled !== "boolean"
    || !Array.isArray(value.enabledTools)
    || value.enabledTools.length > 64
    || value.enabledTools.some((item) => typeof item !== "string" || !toolId.test(item))
    || new Set(value.enabledTools).size !== value.enabledTools.length) {
    throw new ToolSettingsApiError("malformed_response");
  }
  return { enabled: value.enabled, enabledTools: [...value.enabledTools] as string[] };
}

function catalogBody(value: unknown): ToolCatalog {
  if (!record(value) || !exactKeys(value, ["items"]) || !Array.isArray(value.items) || value.items.length > 64) {
    throw new ToolSettingsApiError("malformed_response");
  }
  const items = value.items.map((item): ToolSummary => {
    if (!record(item)
      || !exactKeys(item, ["id", "source", "effect", "available"])
      || typeof item.id !== "string"
      || !toolId.test(item.id)
      || typeof item.source !== "string"
      || !toolSources.includes(item.source as ToolSource)
      || typeof item.effect !== "string"
      || !toolEffects.includes(item.effect as ToolEffect)
      || typeof item.available !== "boolean") {
      throw new ToolSettingsApiError("malformed_response");
    }
    return { id: item.id, source: item.source as ToolSource, effect: item.effect as ToolEffect, available: item.available };
  });
  const ids = items.map((item) => item.id);
  if (ids.join("\0") !== [...new Set(ids)].sort().join("\0")) throw new ToolSettingsApiError("malformed_response");
  return { items };
}

function errorCode(value: unknown, allowed: readonly string[]): ToolSettingsErrorCode {
  if (!record(value)
    || !exactKeys(value, ["error"])
    || !record(value.error)
    || !exactKeys(value.error, ["code", "message", "retryable"])
    || typeof value.error.code !== "string"
    || !serverCodes.includes(value.error.code as (typeof serverCodes)[number])
    || !allowed.includes(value.error.code)
    || typeof value.error.message !== "string"
    || typeof value.error.retryable !== "boolean") {
    throw new ToolSettingsApiError("malformed_response");
  }
  return value.error.code as ToolSettingsErrorCode;
}

async function getJson(path: string, init: RequestInit | undefined, errors: ReadonlyMap<number, readonly string[]>): Promise<unknown> {
  let response: Response;
  try { response = await apiFetch(path, init); } catch { throw new ToolSettingsApiError("network_error"); }
  let body: unknown;
  try { body = await response.json(); } catch { throw new ToolSettingsApiError("malformed_response"); }
  if (response.status !== 200) {
    if (response.ok) throw new ToolSettingsApiError("malformed_response");
    throw new ToolSettingsApiError(errorCode(body, errors.get(response.status) ?? []));
  }
  return body;
}

const readErrors = new Map([[503, ["settings_store_unavailable"]], [500, ["internal_error"]]]);

export async function getToolCatalog(): Promise<ToolCatalog> {
  return catalogBody(await getJson("/api/tools", undefined, readErrors));
}

export async function getToolSettings(): Promise<ToolSettings> {
  return settingsBody(await getJson("/api/settings/tools", undefined, readErrors));
}

export async function putToolSettings(settings: ToolSettings): Promise<ToolSettings> {
  const errors = new Map([[400, ["invalid_request", "tool_not_found"]], [503, ["settings_store_unavailable"]], [500, ["internal_error"]]]);
  return settingsBody(await getJson("/api/settings/tools", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) }, errors));
}

export function toolSettingsErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof ToolSettingsApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "error.tools.invalidRequest",
    tool_not_found: "error.tools.notFound",
    settings_store_unavailable: "error.tools.settingsStore",
    internal_error: "error.tools.internal",
    malformed_response: "error.tools.malformed",
    network_error: "error.network",
  } satisfies Record<ToolSettingsErrorCode, MessageKey>;
  return t(keys[code]);
}
import { apiFetch } from "./http";
