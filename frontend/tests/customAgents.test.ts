import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AgentApiError,
  batchAgents,
  createAgent,
  deleteAgent,
  getAgent,
  getAgentSettings,
  listAgents,
  scanAgents,
  setAgentEnabled,
  setAgentSettings,
  updateAgent,
  type CustomAgent,
} from "../src/api/customAgents";

const globalId = "11111111-1111-4111-8111-111111111111";
const workspaceId = "22222222-2222-4222-8222-222222222222";
const agent: CustomAgent = {
  id: globalId,
  scope: "global",
  workspaceId: null,
  fileName: "code-review.toml",
  name: "code-review",
  description: "Review code for correctness and maintainability.",
  revision: 1,
  enabled: true,
  reason: "effective",
  shadowedByAgentId: null,
  providerId: null,
  model: null,
  contentHash: "a".repeat(64),
};
const detail = { ...agent, developerInstructions: "Review it carefully", content: 'name = "code-review"\ndescription = "Review code"\ndeveloper_instructions = "Review it carefully"\n' };

afterEach(() => vi.unstubAllGlobals());

describe("custom Agents API", () => {
  it("reads and updates the master setting with the expected catalog revision", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ enabled: true, revision: 2 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ enabled: false, revision: 3 })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAgentSettings()).resolves.toEqual({ enabled: true, revision: 2 });
    await expect(setAgentSettings({ enabled: false, expectedRevision: 2 })).resolves.toEqual({ enabled: false, revision: 3 });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/agents/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: false, expectedRevision: 2 }),
    });
  });

  it("uses scope-bounded cursor pagination and validates the list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ revision: 4, items: [agent], nextCursor: "next-page" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listAgents("workspace", workspaceId, "previous-page", 25)).resolves.toEqual({ revision: 4, items: [agent], nextCursor: "next-page" });
    expect(fetchMock).toHaveBeenCalledWith(`/api/agents?scope=workspace&workspaceId=${workspaceId}&cursor=previous-page&limit=25`, undefined);
  });

  it("supports create, detail, update, enable, scan, batch, and delete", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(agent), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(detail)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...agent, revision: 2, description: "Updated" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...agent, revision: 3, enabled: false, reason: "disabled" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 4, added: 2 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 5, affected: 1 })))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createAgent({ scope: "global", workspaceId: null, content: detail.content, expectedRevision: 0 })).resolves.toEqual(agent);
    await expect(getAgent(globalId)).resolves.toEqual(detail);
    await expect(updateAgent({ id: globalId, content: detail.content, expectedRevision: 1 })).resolves.toMatchObject({ revision: 2, description: "Updated" });
    await expect(setAgentEnabled({ id: globalId, enabled: false, expectedRevision: 2 })).resolves.toMatchObject({ revision: 3, enabled: false });
    await expect(scanAgents({ scope: "global", workspaceId: null, expectedRevision: 3 })).resolves.toEqual({ revision: 4, added: 2 });
    await expect(batchAgents({ scope: "global", workspaceId: null, ids: [globalId], action: "disable", expectedRevision: 4 })).resolves.toEqual({ revision: 5, affected: 1 });
    await expect(deleteAgent({ id: globalId, expectedRevision: 5 })).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "global", workspaceId: null, content: detail.content, expectedRevision: 0 }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(6, "/api/agents/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "global", workspaceId: null, ids: [globalId], action: "disable", expectedRevision: 4 }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(7, `/api/agents/${globalId}?expectedRevision=5`, { method: "DELETE" });
  });

  it.each([
    { revision: 1, items: [{ ...agent, extra: true }], nextCursor: null },
    { revision: 1, items: [{ ...agent, reason: "secret" }], nextCursor: null },
    { revision: 1, items: [{ ...agent, workspaceId: workspaceId }], nextCursor: null },
    { revision: 1, items: [agent, agent], nextCursor: null },
    { revision: 1, items: [], nextCursor: "" },
    { revision: -1, items: [], nextCursor: null },
  ])("rejects malformed Agent list responses", async raw => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(raw))));
    await expect(listAgents("global")).rejects.toEqual(new AgentApiError("malformed_response"));
  });

  it.each([
    { ...agent, extra: true },
    { ...agent, fileName: "../escape.toml" },
    { ...agent, contentHash: "secret" },
    { ...agent, shadowedByAgentId: "not-a-uuid" },
  ])("rejects malformed Agent success records", async raw => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(raw), { status: 201 })));
    await expect(createAgent({ scope: "global", workspaceId: null, content: detail.content, expectedRevision: 0 })).rejects.toEqual(new AgentApiError("malformed_response"));
  });

  it("rejects unknown or malformed errors instead of exposing server data", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "private_backend_error", message: "private", retryable: false } }), { status: 500 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "revision_conflict", message: "safe", retryable: false, leaked: true } }), { status: 409 }))
      .mockResolvedValueOnce(new Response("not json", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAgentSettings()).rejects.toEqual(new AgentApiError("malformed_response"));
    await expect(getAgentSettings()).rejects.toEqual(new AgentApiError("malformed_response"));
    await expect(getAgentSettings()).rejects.toEqual(new AgentApiError("malformed_response"));
  });

  it("maps an authenticated 401 and network failure through the shared HTTP boundary", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "authentication_required", message: "sign in", retryable: false } }), { status: 401 }))
      .mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAgentSettings()).rejects.toEqual(new AgentApiError("authentication_required"));
    await expect(getAgentSettings()).rejects.toEqual(new AgentApiError("network_error"));
  });

  it("rejects invalid scope and mutation inputs before sending a request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(listAgents("workspace", null)).rejects.toEqual(new AgentApiError("invalid_request"));
    await expect(createAgent({ scope: "global", workspaceId: null, content: detail.content, expectedRevision: -1 })).rejects.toEqual(new AgentApiError("invalid_request"));
    await expect(batchAgents({ scope: "global", workspaceId: null, ids: [globalId, globalId], action: "enable", expectedRevision: 0 })).rejects.toEqual(new AgentApiError("invalid_request"));
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
