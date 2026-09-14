import { apiFetch } from "./http";
import { isProviderId, providerIds, type ProviderId } from "./providerConnections";

export type CustomModel = { key: string; model_id: string; name: string; context_limit: number; output_limit: number; tools: boolean; source: "manual" | "discovered" };
export type CustomProvider = { id: ProviderId; name: string; revision: number; protocol: "openai_chat_completions"; base_url: string; auth_mode: "none" | "bearer"; allow_insecure_local: boolean; non_streaming_tools?: boolean; created_at: string; updated_at: string; models: CustomModel[] };
export type ProviderDraft = { name: string; baseUrl: string; protocol: "openai_chat_completions"; authMode: "none" | "bearer"; allowInsecureLocal: boolean; nonStreamingTools?: boolean; apiKey?: string; expectedRevision: number };
export type ModelDraft = { modelId: string; name: string; contextLimit: number; outputLimit: number; tools: boolean; expectedRevision: number };
export class CustomProviderApiError extends Error {
  constructor(readonly code: string) { super(code); this.name = "CustomProviderApiError"; }
}
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const exact = (v: Record<string, unknown>, keys: string[]) => Object.keys(v).length === keys.length && keys.every((key) => Object.hasOwn(v, key));
const integer = (v: unknown, min: number): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= min;
const text = (v: unknown, max: number): v is string => typeof v === "string" && Array.from(v).length > 0 && Array.from(v).length <= max;
const customId = (v: unknown): v is ProviderId => isProviderId(v) && !providerIds.includes(v);
const fail = (): never => { throw new CustomProviderApiError("malformed_response"); };

function model(value: unknown): CustomModel {
  if (!record(value) || !exact(value, ["key", "model_id", "name", "context_limit", "output_limit", "tools", "source"])
    || !customId(value.key) || !text(value.model_id, 256) || !text(value.name, 256)
    || !integer(value.context_limit, 1024) || !integer(value.output_limit, 1) || value.output_limit > value.context_limit
    || typeof value.tools !== "boolean" || (value.source !== "manual" && value.source !== "discovered")) return fail();
  return { key: value.key, model_id: value.model_id, name: value.name, context_limit: value.context_limit, output_limit: value.output_limit, tools: value.tools, source: value.source };
}
function models(value: unknown): CustomModel[] {
  if (!Array.isArray(value)) return fail();
  const result = value.map(model);
  if (new Set(result.map((item) => item.key)).size !== result.length || new Set(result.map((item) => item.model_id)).size !== result.length) return fail();
  return result;
}
function provider(value: unknown): CustomProvider {
  if (!record(value) || !exact(value, ["id", "name", "revision", "protocol", "base_url", "auth_mode", "allow_insecure_local", "created_at", "updated_at", "models", ...("non_streaming_tools" in value ? ["non_streaming_tools"] : [])])
    || ("non_streaming_tools" in value && typeof value.non_streaming_tools !== "boolean")
    || !customId(value.id) || !text(value.name, 80) || !integer(value.revision, 1) || value.protocol !== "openai_chat_completions"
    || typeof value.base_url !== "string" || !/^https?:\/\//.test(value.base_url)
    || (value.auth_mode !== "none" && value.auth_mode !== "bearer") || typeof value.allow_insecure_local !== "boolean"
    || typeof value.created_at !== "string" || !Number.isFinite(Date.parse(value.created_at))
    || typeof value.updated_at !== "string" || !Number.isFinite(Date.parse(value.updated_at))) return fail();
  return { id: value.id, name: value.name, revision: value.revision, protocol: value.protocol, base_url: value.base_url,
    auth_mode: value.auth_mode, allow_insecure_local: value.allow_insecure_local, created_at: value.created_at,
    updated_at: value.updated_at, models: models(value.models), ...(typeof value.non_streaming_tools === "boolean" ? { non_streaming_tools: value.non_streaming_tools } : {}) };
}
function modelList(value: unknown): { revision: number; models: CustomModel[] } {
  if (!record(value) || !exact(value, ["revision", "models"]) || !integer(value.revision, 1)) return fail();
  return { revision: value.revision, models: models(value.models) };
}
const errorStatuses: Readonly<Record<string, number>> = {
  invalid_request: 400, credential_required: 400,
  duplicate_name: 409, duplicate_model: 409, revision_conflict: 409,
  provider_busy: 409, provider_in_use: 409, not_connected: 409,
  provider_not_found: 404, model_not_found: 404,
  invalid_credentials: 422, model_discovery_unsupported: 422,
  provider_rate_limited: 429, provider_unreachable: 502, invalid_provider_response: 502,
  provider_timeout: 504, provider_store_unavailable: 503,
  credential_store_unavailable: 503, provider_references_unavailable: 503,
};
async function request(path: string, method: string, body?: unknown, expectedStatus = 200): Promise<unknown> {
  let response: Response;
  try { response = await apiFetch(path, { method, ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) }); }
  catch { throw new CustomProviderApiError("network_error"); }
  let value: unknown;
  try { value = await response.json(); } catch { return fail(); }
  if (response.status === expectedStatus) return value;
  if (response.ok || !record(value) || !exact(value, ["error"]) || !record(value.error)
    || !exact(value.error, ["code", "message", "retryable"]) || typeof value.error.code !== "string"
    || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean"
    || errorStatuses[value.error.code] !== response.status
    || value.error.retryable !== [429, 502, 503, 504].includes(response.status)) return fail();
  throw new CustomProviderApiError(value.error.code);
}
export async function createCustomProvider(draft: ProviderDraft) { return provider(await request("/api/providers", "POST", draft, 201)); }
export async function listCustomProviders(): Promise<{ revision: number; providers: CustomProvider[] }> {
  const providers: CustomProvider[] = [];
  const seen = new Set<string>();
  let revision: number | undefined;
  let cursor: string | null = null;
  do {
    const value = await request(`/api/providers/catalog${cursor === null ? "" : `?cursor=${encodeURIComponent(cursor)}`}`, "GET");
    if (!record(value) || !exact(value, ["revision", "providers", "nextCursor"]) || !integer(value.revision, 0)
      || !Array.isArray(value.providers) || value.providers.length > 100
      || (value.nextCursor !== null && (typeof value.nextCursor !== "string" || !/^[0-9]{1,16}:[1-9][0-9]{0,15}$/.test(value.nextCursor)))) return fail();
    if (revision !== undefined && revision !== value.revision) throw new CustomProviderApiError("revision_conflict");
    revision = value.revision;
    for (const item of value.providers.map(provider)) {
      if (seen.has(item.id)) return fail();
      seen.add(item.id);
      providers.push(item);
    }
    cursor = value.nextCursor as string | null;
    if (cursor !== null && (value.providers.length === 0 || cursor !== `${revision}:${providers.length}`)) return fail();
  } while (cursor !== null);
  return { revision: revision!, providers };
}
export async function getCustomProvider(id: ProviderId) { return provider(await request(`/api/providers/${encodeURIComponent(id)}`, "GET")); }
export async function updateCustomProvider(id: ProviderId, draft: ProviderDraft) { return provider(await request(`/api/providers/${encodeURIComponent(id)}`, "PUT", draft)); }
export async function deleteCustomProvider(id: ProviderId, expectedRevision: number): Promise<void> {
  const result = await request(`/api/providers/${encodeURIComponent(id)}?expectedRevision=${expectedRevision}`, "DELETE");
  if (!record(result) || !exact(result, ["deleted"]) || result.deleted !== true) fail();
}
export async function updateCustomModel(id: ProviderId, key: string, draft: ModelDraft) {
  return modelList(await request(`/api/providers/${encodeURIComponent(id)}/models/${encodeURIComponent(key)}`, "PUT", draft));
}
export async function deleteCustomModel(id: ProviderId, key: string, expectedRevision: number) {
  return modelList(await request(`/api/providers/${encodeURIComponent(id)}/models/${encodeURIComponent(key)}?expectedRevision=${expectedRevision}`, "DELETE"));
}
export async function listCustomModels(id: ProviderId): Promise<{ revision: number; models: CustomModel[] }> {
  const collected: CustomModel[] = [];
  let revision: number | undefined;
  let cursor: string | null = null;
  do {
    const value = await request(`/api/providers/${encodeURIComponent(id)}/models${cursor === null ? "" : `?cursor=${encodeURIComponent(cursor)}`}`, "GET");
    if (!record(value) || !exact(value, ["revision", "models", "nextCursor"])
      || (value.nextCursor !== null && typeof value.nextCursor !== "string")) return fail();
    const page = modelList({ revision: value.revision, models: value.models });
    if (page.models.length > 100) return fail();
    if (revision !== undefined && revision !== page.revision) throw new CustomProviderApiError("revision_conflict");
    revision = page.revision;
    collected.push(...page.models);
    cursor = value.nextCursor as string | null;
    if (cursor !== null && (page.models.length === 0 || cursor !== `${revision}:${collected.length}`)) return fail();
  } while (cursor !== null);
  return { revision: revision!, models: models(collected) };
}
export async function refreshCustomModels(id: ProviderId, expectedRevision: number) { return modelList(await request(`/api/providers/${encodeURIComponent(id)}/models/refresh`, "POST", { expectedRevision })); }
export async function createCustomModel(id: ProviderId, draft: ModelDraft) { return modelList(await request(`/api/providers/${encodeURIComponent(id)}/models`, "POST", draft, 201)); }
