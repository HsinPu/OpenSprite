import { afterEach, expect, it, vi } from "vitest";
import { listRunEventHistory } from "../src/api/agentChat";
import { diagnosticExport } from "../src/features/chat/diagnosticExport";
import { limitErrorCodes } from "../src/api/runLimits";

const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const error = { code: "model_request_limit_reached", message: "Limit", retryable: false };
const limit = { kind: "model_requests", maximum: 128, used: 128 };
afterEach(() => vi.unstubAllGlobals());
function respond(data: object, type = "run.failed") {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ events: [
    { sequence: 1, type, runId, conversationId, createdAt: "2026-10-09T12:00:00Z", data },
  ], nextAfterSequence: null }))));
}

it.each(Object.entries(limitErrorCodes))("reads and exports %s stop evidence", async (kind, code) => {
  const data = { error: { ...error, code }, limit: { ...limit, kind } };
  respond(data);
  const events = (await listRunEventHistory(runId)).events;
  expect(events[0].data).toEqual(data);
  expect(JSON.parse(diagnosticExport(runId, events, 0, null)).events[0].data).toEqual(data);
});

it("reads the legacy generic limit without adding invented evidence", async () => {
  respond({ error: { ...error, code: "agent_limit_reached" } });
  expect((await listRunEventHistory(runId)).events[0].data).toEqual({ error: { ...error, code: "agent_limit_reached" } });
});

it.each([
  { ...limit, maximum: 0 }, { ...limit, maximum: true }, { ...limit, used: -1 },
  { ...limit, used: 1.5 }, { ...limit, used: "128" }, { ...limit, kind: "duration_seconds" },
  { ...limit, privateText: "must not export" }, { ...limit, used: Number.MAX_SAFE_INTEGER + 1 },
])("rejects malformed or mismatched evidence", async value => {
  respond({ error, limit: value });
  await expect(listRunEventHistory(runId)).rejects.toMatchObject({ code: "malformed_response" });
});

it("rejects evidence on interrupted events and retryable stops", async () => {
  respond({ error, limit }, "run.interrupted");
  await expect(listRunEventHistory(runId)).rejects.toThrow();
  respond({ error: { ...error, retryable: true }, limit });
  await expect(listRunEventHistory(runId)).rejects.toThrow();
});
