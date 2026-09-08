import { afterEach, describe, expect, it, vi } from "vitest";

import { batchSkills, listSkills, SkillApiError } from "../src/api/skills";

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
  it("accepts batch counts above 100", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ revision: 3, completed: 297, skipped: [], failed: [] }))));
    expect((await batchSkills("global", null, "enable", 2)).completed).toBe(297);
  });
  it("sends scope-bounded batch requests", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ revision: 3, completed: 1, skipped: [], failed: [] })));
    vi.stubGlobal("fetch", fetch);
    expect((await batchSkills("global", null, "disable", 2)).completed).toBe(1);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ scope: "global", workspaceId: null, action: "disable", expectedRevision: 2 });
  });

  it.each([
    { revision: 1, completed: 0, skipped: [], failed: [], extra: true },
    { revision: 1, completed: -1, skipped: [], failed: [] },
    { revision: 1, completed: 0, skipped: [{ id: validSkill.id, reason: "secret" }], failed: [] },
    { revision: 1, completed: 0, skipped: [{ id: validSkill.id, reason: "missing" }], failed: [{ id: validSkill.id, reason: "missing" }] },
  ])("rejects malformed batch results", async raw => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(raw))));
    await expect(batchSkills("global", null, "enable", 0)).rejects.toEqual(new SkillApiError("malformed_response"));
  });

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
