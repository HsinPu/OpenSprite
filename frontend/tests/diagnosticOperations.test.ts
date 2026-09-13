import { expect, it } from "vitest";
import { diagnosticOperations } from "../src/features/chat/diagnosticOperations";
import type { RunEvent } from "../src/api/agentChat";

const id = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
function attempt(sequence: number, status: string, attemptId = id): RunEvent {
  return { sequence, runId: id, conversationId: id, createdAt: "2026-09-13T00:00:00Z", type: "model.attempt", data: {
    schemaVersion: 1, requestId: id, attemptId, attemptNumber: 1, purpose: "main",
    retryOfAttemptId: null, retryCause: null, compactionId: null, parentRequestId: null, status,
    ...(status === "completed" ? { finishReason: "final", inputTokens: null, outputTokens: 0 } : {}),
    ...(status === "failed" ? { errorCode: "invalid_credentials" } : {}),
  } };
}
it.each(["completed", "failed", "cancelled"])("groups start and %s without mutating raw events", status => {
  const events = [attempt(1, "started"), attempt(2, status)];
  const original = JSON.stringify(events);
  const rows = diagnosticOperations(events, "failed");
  expect(rows).toHaveLength(1);
  expect(rows[0].status).toBe(status);
  expect(rows[0].start).toBe(events[0]);
  expect(JSON.stringify(events)).toBe(original);
});
it("updates a stable key across pages and deduplicates sequences", () => {
  const start = attempt(1, "started");
  const first = diagnosticOperations([start], "completed", true)[0];
  expect(first.status).toBe("partial");
  const next = diagnosticOperations([start, start, attempt(2, "completed")], "completed")[0];
  expect(next.key).toBe(first.key);
  expect(next.events).toHaveLength(2);
});
it("does not merge equal attempt numbers across runs or attempt IDs", () => {
  const a = attempt(1, "started");
  expect(diagnosticOperations([a, { ...a, runId: "other" }, attempt(2, "started", "49d6c5e3-1724-44a7-9e69-0c0103176461")])).toHaveLength(3);
});
it("never implies a finished or unknown run is still active", () => {
  expect(diagnosticOperations([attempt(1, "started")], "completed")[0].status).toBe("missingEnd");
  expect(diagnosticOperations([attempt(1, "started")])[0].status).toBe("missingEnd");
  expect(diagnosticOperations([attempt(1, "started")], "running")[0].status).toBe("started");
});
it("keeps legacy compaction starts separate", () => {
  const legacy: RunEvent = { ...attempt(1, "started"), type: "context.compaction.started", data: {} };
  expect(diagnosticOperations([legacy, { ...legacy, sequence: 2 }])).toHaveLength(2);
});
it("groups compaction but not its summary model request", () => {
  const start: RunEvent = { ...attempt(1, "started"), type: "context.compaction.started", data: {
    schemaVersion: 1, compactionId: id, reason: "local_budget", fromSequence: 1, throughSequence: 3, estimatedBeforeTokens: 100, inputBudgetTokens: 50,
  } };
  const end: RunEvent = { ...start, sequence: 3, type: "context.compaction.completed", data: { schemaVersion: 1, compactionId: id, throughSequence: 3, inputTokens: 100, outputTokens: 20 } };
  const summary = attempt(2, "started");
  summary.data.purpose = "compaction"; summary.data.compactionId = id; summary.data.parentRequestId = id;
  const rows = diagnosticOperations([start, summary, end]);
  expect(rows).toHaveLength(2);
  expect(rows[0].status).toBe("completed");
});
