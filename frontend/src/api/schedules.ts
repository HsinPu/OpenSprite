import type {
  ContextBudget,
  OutputBudget,
  OutputContinuation,
  PersistedModelSelection,
  ResponseMode,
} from "./aiSettings";
import { apiFetch } from "./http";

export type ScheduleStatus = "active" | "paused" | "completed";
export type OccurrenceStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type ScheduleCadence =
  | { type: "once"; runAt: string }
  | { type: "daily"; localTime: string }
  | { type: "weekly"; localTime: string; weekdays: number[] };
export type ScheduleExecutionProfile = PersistedModelSelection & {
  responseMode: ResponseMode;
  outputContinuation: OutputContinuation;
};
export type ScheduleFields = {
  workspaceId: string;
  name: string;
  prompt: string;
  timeZone: string;
  cadence: ScheduleCadence;
  executionProfile: ScheduleExecutionProfile;
};
export type Occurrence = {
  id: string;
  scheduleId: string;
  scheduledFor: string;
  trigger: "manual" | "scheduled";
  status: OccurrenceStatus;
  runId: string | null;
  errorCode: string | null;
  missedCount: number;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
};
export type Schedule = ScheduleFields & {
  id: string;
  status: ScheduleStatus;
  conversationId: string | null;
  nextRunAt: string | null;
  revision: number;
  createdAt: string;
  updatedAt: string;
  latestOccurrence: Occurrence | null;
};
export type SchedulePage = { schedules: Schedule[]; nextCursor: string | null };
export type OccurrencePage = { occurrences: Occurrence[]; nextCursor: string | null };
export type ScheduleRuntimeStatus = {
  platform: string;
  continuity: "linger_enabled" | "login_only" | "unknown";
};
export type ScheduleApiErrorCode =
  | "invalid_request"
  | "not_found"
  | "revision_conflict"
  | "database_unavailable"
  | "workspace_not_found"
  | "workspace_store_unavailable"
  | "workspace_busy"
  | "network_error"
  | "malformed_response";

export class ScheduleApiError extends Error {
  constructor(readonly code: ScheduleApiErrorCode) {
    super(code);
    this.name = "ScheduleApiError";
  }
}

const identifier = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const responseModes = ["default", "fast", "balanced", "deep"] as const;
const contextBudgets = ["auto", "32k", "64k", "128k", "256k", "max"] as const;
const outputBudgets = ["auto", "8k", "16k", "32k", "64k", "max"] as const;
const continuations = ["off", "1", "2", "3", "5", "10", "20", "50", "unlimited"] as const;
const providers = ["openai", "anthropic", "openrouter"] as const;
const statuses = ["active", "paused", "completed"] as const;
const occurrenceStatuses = ["pending", "running", "completed", "failed", "skipped"] as const;
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exact = (value: Record<string, unknown>, keys: readonly string[]) => Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));
const oneOf = <T extends string>(value: unknown, values: readonly T[]): value is T => typeof value === "string" && values.includes(value as T);
const dateString = (value: unknown): value is string => typeof value === "string" && Number.isFinite(Date.parse(value));

function cadence(value: unknown): ScheduleCadence {
  if (!record(value) || typeof value.type !== "string") throw new ScheduleApiError("malformed_response");
  if (value.type === "once" && exact(value, ["type", "runAt"]) && dateString(value.runAt)) return { type: "once", runAt: value.runAt };
  if (value.type === "daily" && exact(value, ["type", "localTime"]) && typeof value.localTime === "string") return { type: "daily", localTime: value.localTime };
  if (value.type === "weekly" && exact(value, ["type", "localTime", "weekdays"]) && typeof value.localTime === "string" && Array.isArray(value.weekdays) && value.weekdays.every((day) => Number.isInteger(day) && day >= 1 && day <= 7)) return { type: "weekly", localTime: value.localTime, weekdays: value.weekdays as number[] };
  throw new ScheduleApiError("malformed_response");
}

function profile(value: unknown): ScheduleExecutionProfile {
  if (!record(value) || !exact(value, ["providerId", "modelId", "responseMode", "contextBudget", "outputBudget", "outputContinuation"]) || !oneOf(value.providerId, providers) || typeof value.modelId !== "string" || !value.modelId || !oneOf(value.responseMode, responseModes) || !oneOf(value.contextBudget, contextBudgets) || !oneOf(value.outputBudget, outputBudgets) || !oneOf(value.outputContinuation, continuations)) throw new ScheduleApiError("malformed_response");
  return value as ScheduleExecutionProfile;
}

function schedule(value: unknown): Schedule {
  const keys = ["id", "workspaceId", "name", "prompt", "timeZone", "cadence", "executionProfile", "status", "conversationId", "nextRunAt", "revision", "createdAt", "updatedAt", "latestOccurrence"];
  if (!record(value) || !exact(value, keys) || typeof value.id !== "string" || !identifier.test(value.id) || typeof value.workspaceId !== "string" || !identifier.test(value.workspaceId) || typeof value.name !== "string" || typeof value.prompt !== "string" || typeof value.timeZone !== "string" || !oneOf(value.status, statuses) || !(value.conversationId === null || (typeof value.conversationId === "string" && identifier.test(value.conversationId))) || !(value.nextRunAt === null || dateString(value.nextRunAt)) || !Number.isInteger(value.revision) || (value.revision as number) < 1 || !dateString(value.createdAt) || !dateString(value.updatedAt)) throw new ScheduleApiError("malformed_response");
  if (!(value.latestOccurrence === null || record(value.latestOccurrence))) throw new ScheduleApiError("malformed_response");
  return { ...value, cadence: cadence(value.cadence), executionProfile: profile(value.executionProfile), latestOccurrence: value.latestOccurrence === null ? null : occurrence(value.latestOccurrence) } as Schedule;
}

function occurrence(value: unknown): Occurrence {
  const keys = ["id", "scheduleId", "scheduledFor", "trigger", "status", "runId", "errorCode", "missedCount", "startedAt", "finishedAt", "createdAt"];
  if (!record(value) || !exact(value, keys) || typeof value.id !== "string" || !identifier.test(value.id) || typeof value.scheduleId !== "string" || !identifier.test(value.scheduleId) || !dateString(value.scheduledFor) || !oneOf(value.trigger, ["manual", "scheduled"] as const) || !oneOf(value.status, occurrenceStatuses) || !(value.runId === null || (typeof value.runId === "string" && identifier.test(value.runId))) || !(value.errorCode === null || typeof value.errorCode === "string") || !Number.isInteger(value.missedCount) || (value.missedCount as number) < 0 || !(value.startedAt === null || dateString(value.startedAt)) || !(value.finishedAt === null || dateString(value.finishedAt)) || !dateString(value.createdAt)) throw new ScheduleApiError("malformed_response");
  return value as Occurrence;
}

async function response(request: Promise<Response>): Promise<unknown> {
  let resolved: Response;
  try { resolved = await request; } catch { throw new ScheduleApiError("network_error"); }
  let body: unknown = null;
  if (resolved.status !== 204) {
    try { body = await resolved.json(); } catch { throw new ScheduleApiError("malformed_response"); }
  }
  if (!resolved.ok) {
    if (record(body) && exact(body, ["error"]) && record(body.error) && exact(body.error, ["code", "message", "retryable"]) && typeof body.error.code === "string" && ["invalid_request", "not_found", "revision_conflict", "database_unavailable", "workspace_not_found", "workspace_store_unavailable", "workspace_busy"].includes(body.error.code)) throw new ScheduleApiError(body.error.code as ScheduleApiErrorCode);
    throw new ScheduleApiError("malformed_response");
  }
  return body;
}

export async function listSchedules(): Promise<SchedulePage> {
  const body = await response(apiFetch("/api/schedules?limit=100"));
  if (!record(body) || !exact(body, ["schedules", "nextCursor"]) || !Array.isArray(body.schedules) || !(body.nextCursor === null || typeof body.nextCursor === "string")) throw new ScheduleApiError("malformed_response");
  return { schedules: body.schedules.map(schedule), nextCursor: body.nextCursor };
}

export async function createSchedule(fields: ScheduleFields): Promise<Schedule> {
  return schedule(await response(apiFetch("/api/schedules", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields) })));
}

export async function updateSchedule(item: Schedule, fields: ScheduleFields): Promise<Schedule> {
  return schedule(await response(apiFetch(`/api/schedules/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...fields, revision: item.revision }) })));
}

export async function setSchedulePaused(item: Schedule, paused: boolean): Promise<Schedule> {
  return schedule(await response(apiFetch(`/api/schedules/${item.id}/${paused ? "pause" : "resume"}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision: item.revision }) })));
}

export async function runScheduleNow(id: string): Promise<Occurrence> {
  return occurrence(await response(apiFetch(`/api/schedules/${id}/run-now`, { method: "POST" })));
}

export async function deleteSchedule(id: string): Promise<void> {
  await response(apiFetch(`/api/schedules/${id}`, { method: "DELETE" }));
}

export async function listScheduleOccurrences(id: string): Promise<OccurrencePage> {
  const body = await response(apiFetch(`/api/schedules/${id}/occurrences?limit=100`));
  if (!record(body) || !exact(body, ["occurrences", "nextCursor"]) || !Array.isArray(body.occurrences) || !(body.nextCursor === null || typeof body.nextCursor === "string")) throw new ScheduleApiError("malformed_response");
  return { occurrences: body.occurrences.map(occurrence), nextCursor: body.nextCursor };
}

export async function getScheduleRuntimeStatus(): Promise<ScheduleRuntimeStatus> {
  const body = await response(apiFetch("/api/schedules/runtime-status"));
  if (!record(body) || !exact(body, ["platform", "continuity"]) || typeof body.platform !== "string" || !oneOf(body.continuity, ["linger_enabled", "login_only", "unknown"] as const)) throw new ScheduleApiError("malformed_response");
  return body as ScheduleRuntimeStatus;
}

export type { ContextBudget, OutputBudget };
