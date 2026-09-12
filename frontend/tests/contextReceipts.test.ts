import { expect, it } from "vitest";
import { validContextReceipt } from "../src/api/contextReceipts";
import { validAttemptPayload } from "../src/api/attemptEvents";

const id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const receipt = {
  schemaVersion: 1, requestHash: "a".repeat(64), estimateMethod: "utf8-conservative-v1",
  estimatedInputTokens: 3, components: { system: 0, summary: 0, history: 0, currentUser: 0, toolResults: 0, assistant: 0, summaryInput: 0, unattributed: 0, toolDefinitions: 0, framing: 3 },
  contextLimitTokens: null, inputBudgetTokens: null, outputReserveTokens: 32,
  messageCount: 1, toolCount: 0, systemHash: "b".repeat(64), toolsHash: "c".repeat(64),
  historyMessageIds: [id], summary: null, skills: [], workspace: null,
};
it("accepts bounded receipts through the attempt parser", () => {
  expect(validContextReceipt(receipt)).toBe(true);
  expect(validAttemptPayload({ schemaVersion: 1, requestId: id, attemptId: id, attemptNumber: 1, purpose: "main", retryOfAttemptId: null, retryCause: null, compactionId: null, parentRequestId: null, status: "started", context: receipt })).toBe(true);
});
it("rejects leaked content, inconsistent sums, and unbounded source lists", () => {
  expect(validContextReceipt({ ...receipt, prompt: "secret" })).toBe(false);
  expect(validContextReceipt({ ...receipt, estimatedInputTokens: 4 })).toBe(false);
  expect(validContextReceipt({ ...receipt, historyMessageIds: [id, id] })).toBe(false);
  expect(validContextReceipt({ ...receipt, workspace: { id, revision: 1, mountManifestHash: "a".repeat(64), path: "private" } })).toBe(false);
  expect(validContextReceipt({ ...receipt, skills: [{ id, revision: 1, contentHash: "a".repeat(64), body: "secret" }] })).toBe(false);
});
