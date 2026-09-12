import { expect, it } from "vitest";
import { validCompactionPayload } from "../src/api/compactionEvents";

const common = { schemaVersion: 1, compactionId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" };
it.each([
  ["started", { reason: "local_budget", fromSequence: 1, throughSequence: 10, estimatedBeforeTokens: 9000, inputBudgetTokens: 8000 }],
  ["completed", { throughSequence: 10, inputTokens: 9000, outputTokens: 100 }],
  ["failed", { errorCode: "context_limit" }],
  ["cancelled", { reason: "cancelled" }],
])("validates %s metadata without allowing private content", (suffix, fields) => {
  const type = `context.compaction.${suffix}`;
  const data = { ...common, ...fields };
  expect(validCompactionPayload(type, data)).toBe(true);
  expect(validCompactionPayload(type, { ...data, prompt: "secret" })).toBe(false);
  expect(validCompactionPayload(type, { ...data, schemaVersion: true })).toBe(false);
  expect(validCompactionPayload(type, { ...data, compactionId: "bad" })).toBe(false);
});
it("accepts only legacy starts and rejects invalid token counts", () => {
  expect(validCompactionPayload("context.compaction.started", {})).toBe(true);
  expect(validCompactionPayload("context.compaction.completed", {})).toBe(false);
  for (const inputTokens of [-1, true, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    expect(validCompactionPayload("context.compaction.completed", { ...common, throughSequence: 1, inputTokens, outputTokens: 1 })).toBe(false);
  }
});
