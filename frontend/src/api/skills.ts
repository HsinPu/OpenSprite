import { apiFetch } from "./http";

export type SkillScope = "global" | "workspace";
export const skillStateLabels = {
  ready: "skills.ready", disabled: "skills.disabled",
  missing: "skills.missing", invalid_format: "skills.invalidFormat", content_too_large: "skills.tooLarge",
  unsafe_path: "skills.unsafePath", workspace_unavailable: "skills.workspaceUnavailable",
  master_disabled: "skills.masterDisabled", shadowed_by_workspace: "skills.shadowed", duplicate_name: "skills.nameConflict",
} as const;
export type Skill = {
  id: string; scope: SkillScope; workspaceId: string | null; directoryName: string;
  name: string; description: string; revision: number; enabled: boolean;
  confirmedHash: string | null; shadowedBySkillId: string | null;
  contentHash: string | null; state: string; effective: boolean; reason: string; content?: string | null;
};
export type SkillList = { revision: number; enabled: boolean; skills: Skill[] };
export type SkillBatchAction = "enable" | "disable" | "archive";
export type SkillBatchResult = { revision: number; completed: number; skipped: { id: string; reason: string }[]; failed: { id: string; reason: string }[] };
export class SkillApiError extends Error {}
const identifier = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const errorCodes = new Set([
  "authentication_required", "rate_limited", "internal_error",
  "invalid_request", "store_unavailable", "not_found", "revision_conflict", "content_changed",
  "duplicate_name", "limit_reached", "skill_limit_reached", "workspace_unavailable", "unsafe_path", "missing",
  "content_too_large", "invalid_format", "directory_exists", "skill_unavailable",
  "file_count_exceeded", "directory_depth_exceeded", "noncanonical_path", "excluded_directory",
  "nested_skill", "invalid_entrypoint", "duplicate_path", "missing_entrypoint",
  "invalid_directory_name", "package_too_large", "invalid_zip", "encrypted_zip", "unsupported_zip", "file_too_large",
]);
const states = new Set(["ready", "disabled", "missing", "invalid_format", "content_too_large", "unsafe_path", "workspace_unavailable", "duplicate_name"]);
const reasons = new Set([...states, "master_disabled", "shadowed_by_workspace"]);
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new SkillApiError("malformed_response");
  return value as Record<string, unknown>;
}
function keys(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  if (required.some(key => !Object.hasOwn(value, key)) || Object.keys(value).some(key => !required.includes(key) && !optional.includes(key))) throw new SkillApiError("malformed_response");
}
function bounded(value: unknown, minimum: number, maximum: number): value is string {
  return typeof value === "string" && [...value].length >= minimum && [...value].length <= maximum;
}
function parseError(value: unknown, allowPath: boolean): string {
  const body = record(value);
  keys(body, ["error"]);
  const error = record(body.error);
  keys(error, ["code", "message", "retryable"], allowPath ? ["path"] : []);
  if (typeof error.code !== "string" || !errorCodes.has(error.code) || typeof error.message !== "string"
    || typeof error.retryable !== "boolean" || (error.path !== undefined && typeof error.path !== "string")) {
    throw new SkillApiError("malformed_response");
  }
  return error.code;
}
function skill(value: unknown): Skill {
  const item = record(value);
  const text = ["id", "directoryName", "name", "description", "state", "reason"];
  keys(item, [...text, "scope", "workspaceId", "revision", "enabled", "confirmedHash", "shadowedBySkillId", "contentHash", "effective"], ["content"]);
  if (typeof item.id !== "string" || !identifier.test(item.id) || typeof item.scope !== "string"
    || typeof item.state !== "string" || typeof item.reason !== "string"
    || !bounded(item.directoryName, 1, 80) || !bounded(item.name, 1, 80)
    || typeof item.description !== "string" || item.directoryName !== String(item.directoryName).normalize("NFC")
    || item.name !== String(item.name).normalize("NFC") || !["global", "workspace"].includes(String(item.scope))
    || (item.scope === "global" ? item.workspaceId !== null : typeof item.workspaceId !== "string" || !identifier.test(item.workspaceId))
    || !Number.isInteger(item.revision) || Number(item.revision) < 1 || typeof item.enabled !== "boolean" || typeof item.effective !== "boolean"
    || (item.shadowedBySkillId !== null && (typeof item.shadowedBySkillId !== "string" || !identifier.test(item.shadowedBySkillId)))
    || [item.confirmedHash, item.contentHash].some(hash => hash !== null && (typeof hash !== "string" || !/^[0-9a-f]{64}$/.test(hash)))
    || !states.has(item.state) || !reasons.has(item.reason)
    || (item.content !== undefined && item.content !== null && (typeof item.content !== "string" || new TextEncoder().encode(item.content).byteLength > 65536))) throw new SkillApiError("malformed_response");
  return item as Skill;
}
export async function skillRequest(path: string, method = "GET", body?: unknown): Promise<unknown> {
  const response = await apiFetch(`/api/skills${path}`, { method, ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  const value: unknown = await response.json();
  if (!response.ok) {
    throw new SkillApiError(parseError(value, false));
  }
  if (method !== "GET") {
    if (method === "DELETE") {
      if (value !== null) throw new SkillApiError("malformed_response");
    } else {
      const result = record(value);
      if (!Number.isInteger(result.revision) || Number(result.revision) < 0) throw new SkillApiError("malformed_response");
      if ("skill" in result) { keys(result, ["revision", "skill"]); skill(result.skill); }
      else if ("skills" in result) {
        keys(result, ["revision", "enabled", "skills"]);
        if (typeof result.enabled !== "boolean" || !Array.isArray(result.skills)) throw new SkillApiError("malformed_response");
        result.skills.forEach(skill);
      } else {
        keys(result, ["revision", "enabled"]);
        if (typeof result.enabled !== "boolean") throw new SkillApiError("malformed_response");
      }
    }
  }
  return value;
}
export async function listSkills(scope: SkillScope, workspaceId?: string): Promise<SkillList> {
  const params = new URLSearchParams({ scope, ...(workspaceId ? { workspaceId } : {}) });
  const value = record(await skillRequest(`?${params}`));
  keys(value, ["revision", "enabled", "skills"]);
  if (!Number.isInteger(value.revision) || Number(value.revision) < 0 || typeof value.enabled !== "boolean" || !Array.isArray(value.skills)) throw new SkillApiError("malformed_response");
  return { revision: Number(value.revision), enabled: value.enabled, skills: value.skills.map(skill) };
}
export async function getSkill(id: string): Promise<{ revision: number; skill: Skill }> {
  const value = record(await skillRequest(`/${encodeURIComponent(id)}`));
  keys(value, ["revision", "skill"]);
  if (!Number.isInteger(value.revision) || Number(value.revision) < 0) throw new SkillApiError("malformed_response");
  return { revision: Number(value.revision), skill: skill(value.skill) };
}

export async function batchSkills(scope: SkillScope, workspaceId: string | null, action: SkillBatchAction, expectedRevision: number): Promise<SkillBatchResult> {
  const response = await apiFetch("/api/skills/batch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope, workspaceId, action, expectedRevision }) });
  const raw: unknown = await response.json();
  if (!response.ok) throw new SkillApiError(parseError(raw, false));
  const result = record(raw);
  keys(result, ["revision", "completed", "skipped", "failed"]);
  if (!Number.isSafeInteger(result.revision) || Number(result.revision) < 0 || !Number.isSafeInteger(result.completed) || Number(result.completed) < 0) throw new SkillApiError("malformed_response");
  const ids = new Set<string>();
  for (const name of ["skipped", "failed"] as const) {
    if (!Array.isArray(result[name])) throw new SkillApiError("malformed_response");
    for (const value of result[name]) {
      const issue = record(value); keys(issue, ["id", "reason"]);
      if (typeof issue.id !== "string" || !identifier.test(issue.id) || ids.has(issue.id) || typeof issue.reason !== "string" || !["unchanged", "missing", "invalid_format", "content_too_large", "unsafe_path", "workspace_unavailable", "duplicate_name"].includes(issue.reason)) throw new SkillApiError("malformed_response");
      ids.add(issue.id);
    }
  }
  return result as SkillBatchResult;
}

export async function importSkillZip(scope: SkillScope, workspaceId: string | null, directoryName: string,
  archive: File, expectedRevision: number): Promise<{ revision: number; skill: Skill }> {
  const body = new FormData();
  body.append("manifest", JSON.stringify({ scope, workspaceId, directoryName, expectedRevision }));
  body.append("archive", archive, "skill.zip");
  const response = await apiFetch("/api/skills/import-zip", { method: "POST", body });
  const raw: unknown = await response.json();
  const value = record(raw);
  if (!response.ok) {
    const code = parseError(value, true);
    const error = record(value.error);
    throw new SkillApiError(`${code}${typeof error.path === "string" ? `: ${error.path}` : ""}`);
  }
  keys(value, ["revision", "skill"]);
  if (!Number.isInteger(value.revision) || Number(value.revision) < 0) throw new SkillApiError("malformed_response");
  return { revision: Number(value.revision), skill: skill(value.skill) };
}
