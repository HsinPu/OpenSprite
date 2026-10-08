import { afterEach, expect, it, vi } from "vitest";
import { listRunEventHistory } from "../src/api/agentChat";

const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const profile = { loopId: "standard", loopVersion: "1.0.0", policyId: "no_recovery", policyVersion: "1.0.0", apiVersion: 2 };

afterEach(() => vi.unstubAllGlobals());

function respond(data: object) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    events: [{ sequence: 2, type: "execution.selected", runId, conversationId, createdAt: "2026-10-07T12:00:00Z", data }],
    nextAfterSequence: null,
  }), { status: 200 })));
}

it("reads the actual execution plugin IDs and versions from persisted history", async () => {
  respond(profile);
  expect((await listRunEventHistory(runId)).events[0].data).toEqual(profile);
});

it.each([
  { ...profile, apiVersion: 1 },
  { ...profile, loopId: "../external" },
  { ...profile, policyVersion: "" },
  { ...profile, rawCredential: "private" },
])("rejects unapproved execution event payloads", async data => {
  respond(data);
  await expect(listRunEventHistory(runId)).rejects.toMatchObject({ code: "malformed_response" });
});
