import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";
import { apiFetch } from "./http";

export const UNASSIGNED_WORKSPACE_ID = "00000000-0000-4000-8000-000000000000";

export type WorkspaceAvailability = "available" | "unavailable" | "not_applicable";
export type WorkspaceUnavailableReason = "missing" | "not_directory" | "access_denied" | "unsafe";
export type WorkspaceUsage = {
  conversationCount: number;
  scheduleCount: number;
  activeRunCount: number;
};
export type Workspace = {
  id: string;
  kind: "unassigned" | "directory";
  name: string;
  rootPath: string | null;
  availability: WorkspaceAvailability;
  unavailableReason: WorkspaceUnavailableReason | null;
  revision: number;
  createdAt: string;
  updatedAt: string;
  usage: WorkspaceUsage;
};
export type WorkspaceCatalog = {
  revision: number;
  activeWorkspaceId: string;
  workspaces: Workspace[];
};
export type WorkspaceApiErrorCode =
  | "invalid_request"
  | "unsafe_root"
  | "duplicate_name"
  | "duplicate_root"
  | "revision_conflict"
  | "not_found"
  | "workspace_busy"
  | "workspace_not_empty"
  | "workspace_store_unavailable"
  | "internal_error"
  | "network_error"
  | "malformed_response";

export class WorkspaceApiError extends Error {
  constructor(readonly code: WorkspaceApiErrorCode) {
    super(code);
    this.name = "WorkspaceApiError";
  }
}

const serverCodes: readonly WorkspaceApiErrorCode[] = [
  "invalid_request", "unsafe_root", "duplicate_name", "duplicate_root",
  "revision_conflict", "not_found", "workspace_busy", "workspace_not_empty",
  "workspace_store_unavailable", "internal_error",
];
const identifier = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const utc = (value: unknown) => typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value));
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exact = (value: Record<string, unknown>, keys: readonly string[]) => Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));

function usage(value: unknown): WorkspaceUsage {
  if (!record(value) || !exact(value, ["conversationCount", "scheduleCount", "activeRunCount"]) || Object.values(value).some((item) => !Number.isInteger(item) || (item as number) < 0)) throw new WorkspaceApiError("malformed_response");
  return value as WorkspaceUsage;
}

function workspace(value: unknown): Workspace {
  const keys = ["id", "kind", "name", "rootPath", "availability", "unavailableReason", "revision", "createdAt", "updatedAt", "usage"];
  if (!record(value) || !exact(value, keys) || typeof value.id !== "string" || !identifier.test(value.id) || !["unassigned", "directory"].includes(value.kind as string) || typeof value.name !== "string" || !value.name || value.name.length > 80 || !(value.rootPath === null || (typeof value.rootPath === "string" && value.rootPath.length > 0 && value.rootPath.length <= 32768)) || !["available", "unavailable", "not_applicable"].includes(value.availability as string) || !(value.unavailableReason === null || ["missing", "not_directory", "access_denied", "unsafe"].includes(value.unavailableReason as string)) || !Number.isInteger(value.revision) || (value.revision as number) < 1 || !utc(value.createdAt) || !utc(value.updatedAt)) throw new WorkspaceApiError("malformed_response");
  if ((value.kind === "unassigned") !== (value.rootPath === null) || (value.availability === "unavailable") !== (value.unavailableReason !== null)) throw new WorkspaceApiError("malformed_response");
  return { ...value, usage: usage(value.usage) } as Workspace;
}

function catalog(value: unknown): WorkspaceCatalog {
  if (!record(value) || !exact(value, ["revision", "activeWorkspaceId", "workspaces"]) || !Number.isInteger(value.revision) || (value.revision as number) < 0 || typeof value.activeWorkspaceId !== "string" || !identifier.test(value.activeWorkspaceId) || !Array.isArray(value.workspaces) || value.workspaces.length < 1 || value.workspaces.length > 101) throw new WorkspaceApiError("malformed_response");
  const workspaces = value.workspaces.map(workspace);
  if (!workspaces.some((item) => item.id === value.activeWorkspaceId) || workspaces.filter((item) => item.kind === "unassigned").length !== 1) throw new WorkspaceApiError("malformed_response");
  return { revision: value.revision as number, activeWorkspaceId: value.activeWorkspaceId, workspaces };
}

function errorCode(value: unknown): WorkspaceApiErrorCode {
  if (!record(value) || !exact(value, ["error"]) || !record(value.error) || !exact(value.error, ["code", "message", "retryable"]) || typeof value.error.code !== "string" || !serverCodes.includes(value.error.code as WorkspaceApiErrorCode) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") throw new WorkspaceApiError("malformed_response");
  return value.error.code as WorkspaceApiErrorCode;
}

async function request(path: string, init: RequestInit | undefined, success: number): Promise<unknown> {
  let response: Response;
  try { response = await apiFetch(path, init); } catch { throw new WorkspaceApiError("network_error"); }
  if (response.status === 204) {
    if (success !== 204) throw new WorkspaceApiError("malformed_response");
    return null;
  }
  let body: unknown;
  try { body = await response.json(); } catch { throw new WorkspaceApiError("malformed_response"); }
  if (response.status !== success) {
    if (response.ok) throw new WorkspaceApiError("malformed_response");
    throw new WorkspaceApiError(errorCode(body));
  }
  return body;
}

export async function listWorkspaces(): Promise<WorkspaceCatalog> {
  return catalog(await request("/api/workspaces", undefined, 200));
}

export async function createWorkspace(name: string, rootPath: string, expectedRevision: number): Promise<WorkspaceCatalog> {
  return catalog(await request("/api/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, rootPath, expectedRevision }) }, 201));
}

export async function updateWorkspace(item: Workspace, name: string, rootPath: string): Promise<Workspace> {
  return workspace(await request(`/api/workspaces/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, rootPath, expectedRevision: item.revision }) }, 200));
}

export async function setActiveWorkspace(workspaceId: string, expectedRevision: number): Promise<WorkspaceCatalog> {
  return catalog(await request("/api/workspaces/active", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workspaceId, expectedRevision }) }, 200));
}

export async function deleteWorkspace(item: Workspace): Promise<void> {
  await request(`/api/workspaces/${item.id}?expectedRevision=${item.revision}`, { method: "DELETE" }, 204);
}

export function workspaceErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof WorkspaceApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "workspaces.error.invalid",
    unsafe_root: "workspaces.error.unsafeRoot",
    duplicate_name: "workspaces.error.duplicateName",
    duplicate_root: "workspaces.error.duplicateRoot",
    revision_conflict: "workspaces.error.conflict",
    not_found: "workspaces.error.notFound",
    workspace_busy: "workspaces.error.busy",
    workspace_not_empty: "workspaces.error.notEmpty",
    workspace_store_unavailable: "workspaces.error.store",
    internal_error: "workspaces.error.internal",
    network_error: "error.network",
    malformed_response: "error.chat.malformed",
  } satisfies Record<WorkspaceApiErrorCode, MessageKey>;
  return t(keys[code]);
}
