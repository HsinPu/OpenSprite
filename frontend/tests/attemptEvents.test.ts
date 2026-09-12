import { expect, it } from "vitest";
import { validAttemptPayload } from "../src/api/attemptEvents";

const data = {
  schemaVersion: 1, requestId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  attemptId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", attemptNumber: 1,
  purpose: "main", retryOfAttemptId: null, retryCause: null,
  compactionId: null, parentRequestId: null, status: "started",
};
it("accepts safe identity and rejects private or contradictory metadata", () => {
  expect(validAttemptPayload(data)).toBe(true);
  expect(validAttemptPayload({ ...data, attemptNumber: 2 })).toBe(false);
  expect(validAttemptPayload({ ...data, requestId: "bad" })).toBe(false);
  expect(validAttemptPayload({ ...data, prompt: "secret" })).toBe(false);
  expect(validAttemptPayload({ ...data, attemptNumber: true })).toBe(false);
  expect(validAttemptPayload({ ...data, status: "failed", errorCode: "raw provider secret" })).toBe(false);
});
it("preserves unknown usage separately from zero and accepts bounded retry", () => {
  expect(validAttemptPayload({ ...data, status: "completed", finishReason: "final", inputTokens: null, outputTokens: 0 })).toBe(true);
  expect(validAttemptPayload({ ...data, status: "completed", finishReason: "final", inputTokens: -1, outputTokens: 0 })).toBe(false);
  expect(validAttemptPayload({ ...data, attemptNumber: 2, retryOfAttemptId: data.attemptId, retryCause: "provider_context_limit" })).toBe(true);
});
