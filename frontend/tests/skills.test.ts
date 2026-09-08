import { afterEach, describe, expect, it, vi } from "vitest";

import { listSkills, SkillApiError } from "../src/api/skills";

const validSkill = {
  id: "11111111-1111-4111-8111-111111111111",
  scope: "global",
  workspaceId: null,
  directoryName: "review",
  name: "review",
  description: "Review code",
  revision: 1,
  enabled: false,
  confirmedHash: null,
  shadowedBySkillId: null,
  contentHash: "a".repeat(64),
  state: "disabled",
  effective: false,
  reason: "disabled",
};

afterEach(() => vi.unstubAllGlobals());

describe("Skills API", () => {
  it.each([
    { ...validSkill, id: "not-a-uuid" },
    { ...validSkill, workspaceId: "not-a-uuid" },
    { ...validSkill, name: "" },
    { ...validSkill, shadowedBySkillId: "not-a-uuid" },
    { ...validSkill, id: [validSkill.id] },
    { ...validSkill, scope: ["global"], workspaceId: validSkill.id },
    { ...validSkill, state: ["disabled"] },
    { ...validSkill, disabledWorkspaces: [] },
  ])("rejects malformed Skill responses", async malformed => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ revision: 1, enabled: true, skills: [malformed] }))));

    await expect(listSkills("global")).rejects.toEqual(new SkillApiError("malformed_response"));
  });

  it("rejects undocumented or malformed error responses", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "private_backend_error", message: "private", retryable: false } }), { status: 400 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "invalid_request", message: "safe", retryable: false, leaked: true } }), { status: 400 })));

    await expect(listSkills("global")).rejects.toEqual(new SkillApiError("malformed_response"));
    await expect(listSkills("global")).rejects.toEqual(new SkillApiError("malformed_response"));
  });
});
