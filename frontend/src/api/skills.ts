import { apiFetch } from "./http";

export type SkillScope = "global" | "workspace";
export const skillStateLabels = {
  ready: "skills.ready", pending: "skills.pending", disabled: "skills.disabled",
  missing: "skills.missing", invalid_format: "skills.invalidFormat", content_too_large: "skills.tooLarge",
  unsafe_path: "skills.unsafePath", workspace_unavailable: "skills.workspaceUnavailable",
  master_disabled: "skills.masterDisabled", workspace_disabled: "skills.workspaceDisabled",
} as const;
export type Skill = {
  id: string; scope: SkillScope; workspaceId: string | null; directoryName: string;
  name: string; description: string; revision: number; enabled: boolean;
  confirmedHash: string | null; disabledWorkspaces: string[];
  contentHash: string | null; state: string; effective: boolean; reason: string; content?: string | null;
};
export type SkillList = { revision: number; enabled: boolean; skills: Skill[] };
export class SkillApiError extends Error {}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new SkillApiError("malformed_response");
  return value as Record<string, unknown>;
}
function keys(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  if (required.some(key => !Object.hasOwn(value, key)) || Object.keys(value).some(key => !required.includes(key) && !optional.includes(key))) throw new SkillApiError("malformed_response");
}
function skill(value: unknown): Skill {
  const item = record(value);
  const text = ["id", "directoryName", "name", "description", "state", "reason"];
  keys(item, [...text, "scope", "workspaceId", "revision", "enabled", "confirmedHash", "disabledWorkspaces", "contentHash", "effective"], ["content"]);
  if (text.some(key => typeof item[key] !== "string") || !["global", "workspace"].includes(String(item.scope))
    || !(item.workspaceId === null || typeof item.workspaceId === "string")
    || !Number.isInteger(item.revision) || Number(item.revision) < 1 || typeof item.enabled !== "boolean" || typeof item.effective !== "boolean"
    || !Array.isArray(item.disabledWorkspaces) || item.disabledWorkspaces.some(id => typeof id !== "string")
    || [item.confirmedHash, item.contentHash].some(hash => hash !== null && (typeof hash !== "string" || !/^[0-9a-f]{64}$/.test(hash)))
    || !["ready", "pending", "disabled", "missing", "invalid_format", "content_too_large", "unsafe_path", "workspace_unavailable"].includes(String(item.state))
    || !["ready", "pending", "disabled", "missing", "invalid_format", "content_too_large", "unsafe_path", "workspace_unavailable", "master_disabled", "workspace_disabled"].includes(String(item.reason))
    || (item.content !== undefined && item.content !== null && typeof item.content !== "string")) throw new SkillApiError("malformed_response");
  return item as Skill;
}
export async function skillRequest(path: string, method = "GET", body?: unknown): Promise<unknown> {
  const response = await apiFetch(`/api/skills${path}`, { method, ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  const value: unknown = await response.json();
  if (!response.ok) {
    const code = record(record(value).error).code;
    throw new SkillApiError(typeof code === "string" ? code : "malformed_response");
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
