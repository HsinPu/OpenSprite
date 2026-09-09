import { apiFetch } from "./http";

export const subagentStatuses = ["queued", "running", "cancelling", "completed", "failed", "cancelled", "interrupted", "timed_out"] as const;
export type SubagentStatus = (typeof subagentStatuses)[number];

export type SubagentSummary = {
  id: string;
  parentRunId: string;
  agentId: string;
  name: string;
  revision: number;
  providerId: string;
  modelId: string;
  status: SubagentStatus;
  errorCode: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
};

export type SubagentList = { items: SubagentSummary[] };
export type SubagentResult = {
  childId: string;
  status: SubagentStatus;
  error: string | null;
  text: string;
  nextOffset: number | null;
};

export type SubagentApiErrorCode =
  | "authentication_required"
  | "invalid_request"
  | "not_found"
  | "run_not_active"
  | "run_busy"
  | "database_unavailable"
  | "internal_error"
  | "rate_limited"
  | "network_error"
  | "malformed_response";

export class SubagentApiError extends Error {
  constructor(readonly code: SubagentApiErrorCode) {
    super(code);
    this.name = "SubagentApiError";
  }
}

const identifier = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const errorCode = /^[a-z][a-z0-9_]{0,79}$/;
const serverErrorCodes = new Set<SubagentApiErrorCode>([
  "authentication_required", "invalid_request", "not_found", "run_not_active", "run_busy",
  "database_unavailable", "internal_error", "rate_limited",
]);

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exact = (value: Record<string, unknown>, keys: readonly string[]) => Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));
const bounded = (value: unknown, minimum: number, maximum: number): value is string => typeof value === "string" && [...value].length >= minimum && [...value].length <= maximum;
const utc = (value: unknown): value is string => {
  if (typeof value !== "string") return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(?:([01]\d|2[0-3])):([0-5]\d):([0-5]\d)(?:\.\d+)?Z$/.exec(value);
  if (!match) return false;
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return false;
  const date = new Date(timestamp);
  return date.getUTCFullYear() === Number(match[1])
    && date.getUTCMonth() + 1 === Number(match[2])
    && date.getUTCDate() === Number(match[3])
    && date.getUTCHours() === Number(match[4])
    && date.getUTCMinutes() === Number(match[5])
    && date.getUTCSeconds() === Number(match[6]);
};

function parseError(value: unknown): SubagentApiErrorCode {
  if (!record(value) || !exact(value, ["error"]) || !record(value.error) || !exact(value.error, ["code", "message", "retryable"])
    || typeof value.error.code !== "string" || !serverErrorCodes.has(value.error.code as SubagentApiErrorCode)
    || !bounded(value.error.message, 1, 512) || typeof value.error.retryable !== "boolean") {
    throw new SubagentApiError("malformed_response");
  }
  return value.error.code as SubagentApiErrorCode;
}

function summary(value: unknown, expectedParentRunId: string): SubagentSummary {
  const keys = ["id", "parentRunId", "agentId", "name", "revision", "providerId", "modelId", "status", "errorCode", "createdAt", "startedAt", "finishedAt"];
  if (!record(value) || !exact(value, keys)
    || typeof value.id !== "string" || !identifier.test(value.id)
    || typeof value.parentRunId !== "string" || value.parentRunId !== expectedParentRunId
    || typeof value.agentId !== "string" || !identifier.test(value.agentId)
    || !bounded(value.name, 1, 80) || !Number.isSafeInteger(value.revision) || (value.revision as number) < 1
    || !bounded(value.providerId, 1, 128) || !bounded(value.modelId, 1, 256)
    || !subagentStatuses.includes(value.status as SubagentStatus)
    || (value.errorCode !== null && (typeof value.errorCode !== "string" || !errorCode.test(value.errorCode)))
    || !utc(value.createdAt) || (value.startedAt !== null && !utc(value.startedAt)) || (value.finishedAt !== null && !utc(value.finishedAt))) {
    throw new SubagentApiError("malformed_response");
  }
  return value as SubagentSummary;
}

function list(value: unknown, expectedParentRunId: string): SubagentList {
  if (!record(value) || !exact(value, ["items"]) || !Array.isArray(value.items) || value.items.length > 6) throw new SubagentApiError("malformed_response");
  const seen = new Set<string>();
  const items = value.items.map((item) => {
    const parsed = summary(item, expectedParentRunId);
    if (seen.has(parsed.id)) throw new SubagentApiError("malformed_response");
    seen.add(parsed.id);
    return parsed;
  });
  return { items };
}

function result(value: unknown, expectedChildId: string): SubagentResult {
  if (!record(value) || !exact(value, ["childId", "status", "error", "text", "nextOffset"])
    || typeof value.childId !== "string" || value.childId !== expectedChildId
    || !subagentStatuses.includes(value.status as SubagentStatus)
    || (value.error !== null && !bounded(value.error, 0, 512))
    || !bounded(value.text, 0, 4000)
    || (value.nextOffset !== null && (!Number.isSafeInteger(value.nextOffset) || (value.nextOffset as number) < 0))) {
    throw new SubagentApiError("malformed_response");
  }
  return value as SubagentResult;
}

async function request(path: string, init: RequestInit | undefined, successStatus: number): Promise<unknown> {
  let response: Response;
  try {
    response = await apiFetch(path, init);
  } catch {
    throw new SubagentApiError("network_error");
  }
  let body: unknown;
  try { body = await response.json(); } catch { throw new SubagentApiError("malformed_response"); }
  if (response.status !== successStatus) {
    if (response.ok) throw new SubagentApiError("malformed_response");
    throw new SubagentApiError(parseError(body));
  }
  return body;
}

function validateId(value: string): void {
  if (typeof value !== "string" || !identifier.test(value)) throw new SubagentApiError("invalid_request");
}

export async function listSubagents(parentRunId: string): Promise<SubagentList> {
  validateId(parentRunId);
  return list(await request(`/api/runs/${encodeURIComponent(parentRunId)}/agents`, undefined, 200), parentRunId);
}

export async function getSubagentResult(parentRunId: string, childId: string, offset = 0): Promise<SubagentResult> {
  validateId(parentRunId); validateId(childId);
  if (!Number.isSafeInteger(offset) || offset < 0) throw new SubagentApiError("invalid_request");
  return result(await request(`/api/runs/${encodeURIComponent(parentRunId)}/agents/${encodeURIComponent(childId)}?offset=${offset}`, undefined, 200), childId);
}

export async function cancelSubagent(parentRunId: string, childId: string): Promise<SubagentSummary> {
  validateId(parentRunId); validateId(childId);
  const value = await request(`/api/runs/${encodeURIComponent(parentRunId)}/agents/${encodeURIComponent(childId)}/cancel`, { method: "POST" }, 200);
  return summary(value, parentRunId);
}
