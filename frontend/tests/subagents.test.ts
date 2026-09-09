import { beforeEach, describe, expect, it, vi } from "vitest";

import { cancelSubagent, getSubagentResult, listSubagents } from "../src/api/subagents";

const parentRunId = "11111111-1111-4111-8111-111111111111";
const childId = "22222222-2222-4222-8222-222222222222";
const agentId = "33333333-3333-4333-8333-333333333333";
const summary = {
  id: childId,
  parentRunId,
  agentId,
  name: "reviewer",
  revision: 2,
  providerId: "openai",
  modelId: "gpt-5.6",
  status: "completed",
  errorCode: null,
  createdAt: "2026-09-09T08:00:00Z",
  startedAt: "2026-09-09T08:00:01Z",
  finishedAt: "2026-09-09T08:00:04Z",
};

beforeEach(() => { vi.stubGlobal("fetch", vi.fn()); });

function respond(value: unknown, status = 200): void {
  vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }));
}

describe("subagent API boundary", () => {
  it("validates parent ids and list summaries", async () => {
    respond({ items: [summary] });
    await expect(listSubagents(parentRunId)).resolves.toEqual({ items: [summary] });
    expect(fetch).toHaveBeenCalledWith(`/api/runs/${parentRunId}/agents`, undefined);
    await expect(listSubagents("not-an-id")).rejects.toMatchObject({ code: "invalid_request" });
  });

  it("rejects responses for another parent or with unknown fields", async () => {
    respond({ items: [{ ...summary, parentRunId: agentId }] });
    await expect(listSubagents(parentRunId)).rejects.toMatchObject({ code: "malformed_response" });
    respond({ items: [{ ...summary, extra: true }] });
    await expect(listSubagents(parentRunId)).rejects.toMatchObject({ code: "malformed_response" });
    respond({ items: [{ ...summary, createdAt: "2026-02-30T08:00:00Z" }] });
    await expect(listSubagents(parentRunId)).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("loads bounded result pages and validates the child id", async () => {
    respond({ childId, status: "completed", error: null, text: "plain result", nextOffset: 12 });
    await expect(getSubagentResult(parentRunId, childId)).resolves.toEqual({ childId, status: "completed", error: null, text: "plain result", nextOffset: 12 });
    expect(fetch).toHaveBeenCalledWith(`/api/runs/${parentRunId}/agents/${childId}?offset=0`, undefined);
    respond({ childId: agentId, status: "completed", error: null, text: "", nextOffset: null });
    await expect(getSubagentResult(parentRunId, childId)).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("uses a bodyless POST for cancellation and preserves safe server errors", async () => {
    respond(summary);
    await expect(cancelSubagent(parentRunId, childId)).resolves.toEqual(summary);
    expect(fetch).toHaveBeenCalledWith(`/api/runs/${parentRunId}/agents/${childId}/cancel`, { method: "POST" });
    respond({ error: { code: "unknown_internal_state", message: "bad", retryable: false } }, 500);
    await expect(listSubagents(parentRunId)).rejects.toMatchObject({ code: "malformed_response" });
  });
});
