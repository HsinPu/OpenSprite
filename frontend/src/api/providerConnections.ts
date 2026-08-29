export const providerIds = ["openai", "anthropic", "openrouter"] as const;
export type ProviderId = (typeof providerIds)[number];
export type ProviderStatus = "disconnected" | "connected" | "invalid_credentials" | "provider_unreachable" | "provider_timeout" | "provider_rate_limited" | "credential_store_unavailable";
export type ServerErrorCode = "invalid_request" | "unsupported_provider" | "not_connected" | "invalid_credentials" | "provider_unreachable" | "provider_timeout" | "provider_rate_limited" | "credential_store_unavailable" | "internal_error";
export type ProviderErrorCode = ServerErrorCode | "malformed_response" | "network_error";
export type ProviderSummary = { id: ProviderId; name: "OpenAI" | "Anthropic" | "OpenRouter"; connected: boolean; status: ProviderStatus; credentialPreview: string | null; lastCheckedAt: string | null };
export type OpenRouterModel = { id: string; name: string; contextWindowTokens: number; maxOutputTokens: number | null };
const statuses: readonly ProviderStatus[] = ["disconnected", "connected", "invalid_credentials", "provider_unreachable", "provider_timeout", "provider_rate_limited", "credential_store_unavailable"];
const serverCodes: readonly ServerErrorCode[] = ["invalid_request", "unsupported_provider", "not_connected", "invalid_credentials", "provider_unreachable", "provider_timeout", "provider_rate_limited", "credential_store_unavailable", "internal_error"];
const allow = { list: new Map([[503,["credential_store_unavailable"]],[500,["internal_error"]]]), put: new Map([[400,["invalid_request"]],[404,["unsupported_provider"]],[422,["invalid_credentials"]],[429,["provider_rate_limited"]],[502,["provider_unreachable"]],[503,["credential_store_unavailable"]],[504,["provider_timeout"]],[500,["internal_error"]]]), test: new Map([[400,["invalid_request"]],[404,["unsupported_provider"]],[409,["not_connected"]],[422,["invalid_credentials"]],[429,["provider_rate_limited"]],[502,["provider_unreachable"]],[503,["credential_store_unavailable"]],[504,["provider_timeout"]],[500,["internal_error"]]]), delete: new Map([[404,["unsupported_provider"]],[503,["credential_store_unavailable"]],[500,["internal_error"]]]), openrouterModels: new Map([[400,["invalid_request"]],[409,["not_connected"]],[422,["invalid_credentials"]],[429,["provider_rate_limited"]],[502,["provider_unreachable"]],[503,["credential_store_unavailable"]],[504,["provider_timeout"]],[500,["internal_error"]]]) } as const;
export class ProviderApiError extends Error { constructor(readonly code: ProviderErrorCode) { super(code); this.name = "ProviderApiError"; } }
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const keys = (v: Record<string, unknown>, expected: readonly string[]) => Object.keys(v).length === expected.length && Object.keys(v).every((key) => expected.includes(key));
const codePointLength = (value: string) => Array.from(value).length;
function utc(v: unknown): v is string { const m = typeof v === "string" && /^(\d{4})-(\d{2})-(\d{2})T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(?:\.\d+)?Z$/.exec(v); if (!m) return false; const [y,mo,d,h,mi,s] = m.slice(1,7).map(Number); const date = new Date(Date.UTC(y,mo-1,d,h,mi,s)); return date.getUTCFullYear()===y && date.getUTCMonth()===mo-1 && date.getUTCDate()===d && date.getUTCHours()===h && date.getUTCMinutes()===mi && date.getUTCSeconds()===s; }
function summary(v: unknown, expectedId?: ProviderId): ProviderSummary {
  if (!record(v) || !keys(v, ["id", "name", "connected", "status", "credentialPreview", "lastCheckedAt"])) throw new ProviderApiError("malformed_response");
  const { id, name, connected, status, credentialPreview, lastCheckedAt } = v;
  if (!providerIds.includes(id as ProviderId) || (id === "openai" && name !== "OpenAI") || (id === "anthropic" && name !== "Anthropic") || (id === "openrouter" && name !== "OpenRouter") || typeof connected !== "boolean" || !statuses.includes(status as ProviderStatus) || (credentialPreview !== null && typeof credentialPreview !== "string") || (lastCheckedAt !== null && !utc(lastCheckedAt)) || (expectedId && id !== expectedId)) throw new ProviderApiError("malformed_response");
  if (!connected && (status !== "disconnected" || credentialPreview !== null || lastCheckedAt !== null)) throw new ProviderApiError("malformed_response");
  if (connected && (status === "disconnected" || lastCheckedAt === null)) throw new ProviderApiError("malformed_response");
  return { id, name, connected, status, credentialPreview, lastCheckedAt } as ProviderSummary;
}
function openRouterModel(v: unknown): OpenRouterModel {
  if (!record(v) || !keys(v, ["id", "name", "contextWindowTokens", "maxOutputTokens"]) || typeof v.id !== "string" || codePointLength(v.id) < 1 || codePointLength(v.id) > 256 || typeof v.name !== "string" || codePointLength(v.name) < 1 || codePointLength(v.name) > 256 || !Number.isInteger(v.contextWindowTokens) || (v.contextWindowTokens as number) < 1 || (v.contextWindowTokens as number) > 4_000_000 || (v.maxOutputTokens !== null && (!Number.isInteger(v.maxOutputTokens) || (v.maxOutputTokens as number) < 1 || (v.maxOutputTokens as number) > (v.contextWindowTokens as number)))) throw new ProviderApiError("malformed_response");
  return { id: v.id, name: v.name, contextWindowTokens: v.contextWindowTokens as number, maxOutputTokens: v.maxOutputTokens as number | null };
}
function envelope(v: unknown, codes: readonly string[]): ServerErrorCode { if (!record(v)||!keys(v,["error"])||!record(v.error)||!keys(v.error,["code","message","retryable"])||typeof v.error.code!=="string"||!serverCodes.includes(v.error.code as ServerErrorCode)||!codes.includes(v.error.code)||typeof v.error.message!=="string"||typeof v.error.retryable!=="boolean") throw new ProviderApiError("malformed_response"); return v.error.code as ServerErrorCode; }
async function call(path:string, init:RequestInit|undefined, errors:ReadonlyMap<number,readonly string[]>) { let response:Response; try { response=await fetch(path,init); } catch { throw new ProviderApiError("network_error"); } if (response.status !== 200) { if (response.ok) throw new ProviderApiError("malformed_response"); let errorBody:unknown; try { errorBody=await response.json(); } catch { throw new ProviderApiError("malformed_response"); } throw new ProviderApiError(envelope(errorBody, errors.get(response.status)??[])); } let body:unknown; try { body=await response.json(); } catch { throw new ProviderApiError("malformed_response"); } return body; }
export async function listProviderConnections() { const body=await call("/api/providers",undefined,allow.list); if (!record(body)||!keys(body,["providers"])||!Array.isArray(body.providers)||body.providers.length!==3) throw new ProviderApiError("malformed_response"); return body.providers.map((item,index)=>summary(item,providerIds[index])); }
export async function replaceProviderConnection(id:ProviderId,key:string) { const result=summary(await call(`/api/providers/${id}/connection`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({apiKey:key})},allow.put),id); if(!result.connected||result.status!=="connected") throw new ProviderApiError("malformed_response"); return result; }
export async function testProviderConnection(id:ProviderId) { const result=summary(await call(`/api/providers/${id}/connection/test`,{method:"POST"},allow.test),id); if(!result.connected||result.status!=="connected") throw new ProviderApiError("malformed_response"); return result; }
export async function listOpenRouterModels(): Promise<OpenRouterModel[]> { const body=await call("/api/providers/openrouter/models",{method:"POST"},allow.openrouterModels); if(!record(body)||!keys(body,["models"])||!Array.isArray(body.models)||body.models.length<1||body.models.length>1000) throw new ProviderApiError("malformed_response"); return body.models.map(openRouterModel); }
export async function deleteProviderConnection(id:ProviderId) { let response:Response;try{response=await fetch(`/api/providers/${id}/connection`,{method:"DELETE"});}catch{throw new ProviderApiError("network_error");}if(response.status===204)return;let body:unknown;try{body=await response.json();}catch{throw new ProviderApiError("malformed_response");}throw new ProviderApiError(response.ok?"malformed_response":envelope(body,allow.delete.get(response.status)??[])); }
export function providerErrorText(error: unknown, t: Translator = defaultTranslator) {
  const code = error instanceof ProviderApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "error.provider.invalidRequest",
    unsupported_provider: "error.provider.unsupported",
    not_connected: "error.provider.notConnected",
    invalid_credentials: "error.provider.invalidCredentials",
    provider_unreachable: "error.provider.unreachable",
    provider_timeout: "error.provider.timeout",
    provider_rate_limited: "error.provider.rateLimited",
    credential_store_unavailable: "error.provider.storeUnavailable",
    internal_error: "error.provider.internal",
    malformed_response: "error.provider.malformed",
    network_error: "error.network",
  } satisfies Record<ProviderErrorCode, MessageKey>;
  return t(keys[code]);
}
import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";
