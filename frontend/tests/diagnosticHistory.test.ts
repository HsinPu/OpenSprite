import { afterEach, expect, it, vi } from "vitest";
import { listRunEventHistory, type RunEvent } from "../src/api/agentChat";
import { diagnosticExport } from "../src/features/chat/diagnosticExport";

const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const event = (sequence: number): RunEvent => ({ sequence, runId, conversationId,
  type: "run.cancelled", createdAt: "2026-08-21T08:30:00Z", data: {} });
afterEach(() => vi.unstubAllGlobals());

it("reads later history without the live 500-event cap", async () => {
  const fetcher = vi.fn(async (_url: string) => new Response(JSON.stringify({ events: [event(601)], nextAfterSequence: null })));
  vi.stubGlobal("fetch", fetcher);
  expect((await listRunEventHistory(runId, 600)).events[0].sequence).toBe(601);
  expect(fetcher.mock.calls[0][0]).toContain("afterSequence=600&limit=100");
});

it.each([
  { events: [event(2), event(2)], nextAfterSequence: null },
  { events: [event(3), event(2)], nextAfterSequence: null },
  { events: [event(2)], nextAfterSequence: 3 },
  { events: [], nextAfterSequence: 2 },
  { events: [{ ...event(2), runId: conversationId }], nextAfterSequence: null },
])("rejects inconsistent history pages", async page => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(page))));
  await expect(listRunEventHistory(runId, 1)).rejects.toThrow();
});

it("exports only allowlisted metadata and explicitly describes partial scope", () => {
  const safe = { ...event(2), type: "context.compaction.started" as const, data: {} };
  const privateEvent = { ...event(3), type: "assistant.delta" as const, data: { text: "PRIVATE_CONTENT" } };
  const poisoned = { ...safe, data: { secret: "PRIVATE_CONTENT" } };
  const output = diagnosticExport(runId, [safe, privateEvent, poisoned], 1, 100);
  expect(output).not.toContain("PRIVATE_CONTENT");
  expect(JSON.parse(output)).toMatchObject({ scope: "loaded-page", contentIncluded: false,
    coversCurrentHistory: false, runCompletionAsserted: false });
  expect(JSON.parse(output).events).toHaveLength(1);
});
