import { apiFetch } from "./http";

export type AgentScope = "global" | "workspace";
export const agentScopes = ["global", "workspace"] as const;

export type AgentReason =
  | "effective"
  | "disabled"
  | "master_disabled"
  | "shadowed_by_workspace"
  | "duplicate_name"
  | "missing"
  | "invalid_format"
  | "content_too_large"
  | "unsafe_path"
  | "workspace_unavailable";

export const agentReasons = [
  "effective",
  "disabled",
  "master_disabled",
  "shadowed_by_workspace",
  "duplicate_name",
  "missing",
  "invalid_format",
  "content_too_large",
  "unsafe_path",
  "workspace_unavailable",
] as const;

export type CustomAgent = {
  id: string;
  scope: AgentScope;
  workspaceId: string | null;
  fileName: string;
  name: string;
  description: string;
  revision: number;
  enabled: boolean;
  reason: AgentReason;
  shadowedByAgentId: string | null;
  providerId: string | null;
  model: string | null;
  contentHash: string | null;
};

export type CustomAgentDetail = CustomAgent & { content: string | null; developerInstructions: string | null };
export type AgentList = { revision: number; items: CustomAgent[]; nextCursor: string | null };
export type AgentSettings = { enabled: boolean; revision: number };
export type AgentSettingsInput = { enabled: boolean; expectedRevision: number };
export type AgentScanResult = { revision: number; added: number };
export type AgentBatchAction = "enable" | "disable" | "remove";
export type AgentBatchResult = { revision: number; affected: number };

export type AgentScopeInput = { scope: AgentScope; workspaceId: string | null };
export type AgentCreateInput = AgentScopeInput & { content: string; expectedRevision: number };
export type AgentUpdateInput = { id: string; content: string; expectedRevision: number };
export type AgentEnabledInput = { id: string; enabled: boolean; expectedRevision: number };
export type AgentDeleteInput = { id: string; expectedRevision: number };
export type AgentScanInput = AgentScopeInput & { expectedRevision: number };
export type AgentBatchInput = AgentScopeInput & { ids: string[]; action: AgentBatchAction; expectedRevision: number };

export type AgentApiErrorCode =
  | "authentication_required"
  | "invalid_request"
  | "store_unavailable"
  | "not_found"
  | "revision_conflict"
  | "duplicate_name"
  | "workspace_unavailable"
  | "file_exists"
  | "unsafe_path"
  | "missing"
  | "invalid_format"
  | "content_too_large"
  | "invalid_utf8"
  | "invalid_content"
  | "duplicate_field"
  | "unknown_field"
  | "missing_field"
  | "invalid_name"
  | "invalid_description"
  | "invalid_developer_instructions"
  | "invalid_provider_id"
  | "invalid_model"
  | "provider_model_pair_required"
  | "internal_error"
  | "network_error"
  | "malformed_response";

export class AgentApiError extends Error {
  constructor(readonly code: AgentApiErrorCode) {
    super(code);
    this.name = "AgentApiError";
  }
}

const identifier = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const hash = /^[0-9a-f]{64}$/;
const errorCodes = new Set<AgentApiErrorCode>([
  "authentication_required",
  "invalid_request",
  "store_unavailable",
  "not_found",
  "revision_conflict",
  "duplicate_name",
  "workspace_unavailable",
  "file_exists",
  "unsafe_path",
  "missing",
  "invalid_format",
  "content_too_large",
  "invalid_utf8",
  "invalid_content",
  "duplicate_field",
  "unknown_field",
  "missing_field",
  "invalid_name",
  "invalid_description",
  "invalid_developer_instructions",
  "invalid_provider_id",
  "invalid_model",
  "provider_model_pair_required",
  "internal_error",
]);

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));
}

function validRevision(value: unknown, minimum = 0): value is number {
  return Number.isSafeInteger(value) && (value as number) >= minimum;
}

function validText(value: unknown, minimum = 0, maximum = 65536): value is string {
  return typeof value === "string" && [...value].length >= minimum && [...value].length <= maximum;
}

function validNullableIdentifier(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && identifier.test(value));
}

function scopeInput(scope: AgentScope, workspaceId: string | null): void {
  if (!agentScopes.includes(scope) || (scope === "workspace") !== (workspaceId !== null)) {
    throw new AgentApiError("invalid_request");
  }
  if (workspaceId !== null && !identifier.test(workspaceId)) throw new AgentApiError("invalid_request");
}

function expectedRevision(value: number): void {
  if (!validRevision(value)) throw new AgentApiError("invalid_request");
}

function content(value: string): void {
  if (!validText(value)) throw new AgentApiError("invalid_request");
}

function agentId(value: string): void {
  if (typeof value !== "string" || !identifier.test(value)) throw new AgentApiError("invalid_request");
}

function parseError(value: unknown): AgentApiErrorCode {
  if (!record(value) || !exact(value, ["error"]) || !record(value.error)
    || !exact(value.error, ["code", "message", "retryable"])
    || typeof value.error.code !== "string"
    || !errorCodes.has(value.error.code as AgentApiErrorCode)
    || typeof value.error.message !== "string"
    || typeof value.error.retryable !== "boolean") {
    throw new AgentApiError("malformed_response");
  }
  return value.error.code as AgentApiErrorCode;
}

function parseAgent(value: unknown): CustomAgent {
  const keys = ["id", "scope", "workspaceId", "fileName", "name", "description", "revision", "enabled", "reason", "shadowedByAgentId", "providerId", "model", "contentHash"];
  if (!record(value) || !exact(value, keys)
    || typeof value.id !== "string" || !identifier.test(value.id)
    || !agentScopes.includes(value.scope as AgentScope)
    || !validNullableIdentifier(value.workspaceId)
    || (value.scope === "global" ? value.workspaceId !== null : value.workspaceId === null)
    || !validText(value.fileName, 1, 255) || value.fileName !== value.fileName.normalize("NFC") || value.fileName.includes("/") || value.fileName.includes("\\") || !value.fileName.endsWith(".toml")
    || !validText(value.name, 1, 80) || value.name !== value.name.normalize("NFC")
    || typeof value.description !== "string"
    || !validRevision(value.revision, 1)
    || typeof value.enabled !== "boolean"
    || !agentReasons.includes(value.reason as AgentReason)
    || !validNullableIdentifier(value.shadowedByAgentId)
    || !(value.providerId === null || validText(value.providerId, 1, 1024))
    || !(value.model === null || validText(value.model, 1, 1024))
    || !(value.contentHash === null || (typeof value.contentHash === "string" && hash.test(value.contentHash)))) {
    throw new AgentApiError("malformed_response");
  }
  return value as CustomAgent;
}

function parseAgentDetail(value: unknown): CustomAgentDetail {
  if (!record(value) || !exact(value, ["id", "scope", "workspaceId", "fileName", "name", "description", "revision", "enabled", "reason", "shadowedByAgentId", "providerId", "model", "contentHash", "content", "developerInstructions"])) {
    throw new AgentApiError("malformed_response");
  }
  const { content: definition, developerInstructions, ...summary } = value;
  parseAgent(summary);
  if (definition !== null && !validText(definition, 0, 65536)) throw new AgentApiError("malformed_response");
  if (developerInstructions !== null && !validText(developerInstructions, 1, 65536)) throw new AgentApiError("malformed_response");
  return value as CustomAgentDetail;
}

function parseAgentList(value: unknown): AgentList {
  if (!record(value) || !exact(value, ["revision", "items", "nextCursor"])
    || !validRevision(value.revision)
    || !Array.isArray(value.items)
    || !(value.nextCursor === null || (typeof value.nextCursor === "string" && value.nextCursor.length > 0 && value.nextCursor.length <= 1024))) {
    throw new AgentApiError("malformed_response");
  }
  const seen = new Set<string>();
  const items = value.items.map((item) => {
    const parsed = parseAgent(item);
    if (seen.has(parsed.id)) throw new AgentApiError("malformed_response");
    seen.add(parsed.id);
    return parsed;
  });
  return { revision: value.revision, items, nextCursor: value.nextCursor };
}

function parseSettings(value: unknown): AgentSettings {
  if (!record(value) || !exact(value, ["enabled", "revision"]) || typeof value.enabled !== "boolean" || !validRevision(value.revision)) throw new AgentApiError("malformed_response");
  return value as AgentSettings;
}

function parseScan(value: unknown): AgentScanResult {
  if (!record(value) || !exact(value, ["revision", "added"]) || !validRevision(value.revision) || !validRevision(value.added)) throw new AgentApiError("malformed_response");
  return value as AgentScanResult;
}

function parseBatch(value: unknown): AgentBatchResult {
  if (!record(value) || !exact(value, ["revision", "affected"]) || !validRevision(value.revision) || !validRevision(value.affected)) throw new AgentApiError("malformed_response");
  return value as AgentBatchResult;
}

async function request(path: string, init: RequestInit | undefined, success: number): Promise<unknown> {
  let response: Response;
  try {
    response = await apiFetch(path, init);
  } catch {
    throw new AgentApiError("network_error");
  }
  if (response.status === 204) {
    if (success !== 204) throw new AgentApiError("malformed_response");
    return null;
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new AgentApiError("malformed_response");
  }
  if (response.status !== success) {
    if (response.ok) throw new AgentApiError("malformed_response");
    throw new AgentApiError(parseError(body));
  }
  return body;
}

function json(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export async function getAgentSettings(): Promise<AgentSettings> {
  return parseSettings(await request("/api/agents/settings", undefined, 200));
}

export async function setAgentSettings(input: AgentSettingsInput): Promise<AgentSettings> {
  if (typeof input !== "object" || input === null || typeof input.enabled !== "boolean") throw new AgentApiError("invalid_request");
  expectedRevision(input.expectedRevision);
  return parseSettings(await request("/api/agents/settings", { ...json(input), method: "PUT" }, 200));
}

export async function listAgents(scope: AgentScope, workspaceId: string | null = null, cursor?: string, limit = 50): Promise<AgentList> {
  scopeInput(scope, workspaceId);
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw new AgentApiError("invalid_request");
  if (cursor !== undefined && (typeof cursor !== "string" || cursor.length < 1 || cursor.length > 1024)) throw new AgentApiError("invalid_request");
  const params = new URLSearchParams({ scope });
  if (workspaceId !== null) params.set("workspaceId", workspaceId);
  if (cursor !== undefined) params.set("cursor", cursor);
  params.set("limit", String(limit));
  return parseAgentList(await request(`/api/agents?${params.toString()}`, undefined, 200));
}

export async function createAgent(input: AgentCreateInput): Promise<CustomAgent> {
  scopeInput(input.scope, input.workspaceId);
  expectedRevision(input.expectedRevision);
  content(input.content);
  return parseAgent(await request("/api/agents", json({ scope: input.scope, workspaceId: input.workspaceId, content: input.content, expectedRevision: input.expectedRevision }), 201));
}

export async function getAgent(id: string): Promise<CustomAgentDetail> {
  agentId(id);
  return parseAgentDetail(await request(`/api/agents/${encodeURIComponent(id)}`, undefined, 200));
}

export async function updateAgent(input: AgentUpdateInput): Promise<CustomAgent> {
  agentId(input.id);
  content(input.content);
  expectedRevision(input.expectedRevision);
  return parseAgent(await request(`/api/agents/${encodeURIComponent(input.id)}`, { ...json({ content: input.content, expectedRevision: input.expectedRevision }), method: "PUT" }, 200));
}

export async function setAgentEnabled(input: AgentEnabledInput): Promise<CustomAgent> {
  agentId(input.id);
  if (typeof input.enabled !== "boolean") throw new AgentApiError("invalid_request");
  expectedRevision(input.expectedRevision);
  return parseAgent(await request(`/api/agents/${encodeURIComponent(input.id)}/enabled`, { ...json({ enabled: input.enabled, expectedRevision: input.expectedRevision }), method: "PUT" }, 200));
}

export async function deleteAgent(input: AgentDeleteInput): Promise<void> {
  agentId(input.id);
  expectedRevision(input.expectedRevision);
  await request(`/api/agents/${encodeURIComponent(input.id)}?expectedRevision=${input.expectedRevision}`, { method: "DELETE" }, 204);
}

export async function scanAgents(input: AgentScanInput): Promise<AgentScanResult> {
  scopeInput(input.scope, input.workspaceId);
  expectedRevision(input.expectedRevision);
  return parseScan(await request("/api/agents/scan", json({ scope: input.scope, workspaceId: input.workspaceId, expectedRevision: input.expectedRevision }), 200));
}

export async function batchAgents(input: AgentBatchInput): Promise<AgentBatchResult> {
  scopeInput(input.scope, input.workspaceId);
  expectedRevision(input.expectedRevision);
  if (!Array.isArray(input.ids) || input.ids.length < 1 || input.ids.some((id) => typeof id !== "string" || !identifier.test(id)) || new Set(input.ids).size !== input.ids.length || !["enable", "disable", "remove"].includes(input.action)) throw new AgentApiError("invalid_request");
  return parseBatch(await request("/api/agents/batch", json({ scope: input.scope, workspaceId: input.workspaceId, ids: input.ids, action: input.action, expectedRevision: input.expectedRevision }), 200));
}
