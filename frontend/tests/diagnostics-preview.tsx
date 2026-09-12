// Synthetic, network-isolated manual browser fixture. Not part of the app build.
import { createRoot } from "react-dom/client";
import { RunDiagnostics } from "../src/features/chat/RunDiagnostics";
import type { RunEvent } from "../src/api/agentChat";
const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
window.fetch = async (input) => {
  const cursor = Number(new URL(String(input), location.origin).searchParams.get("afterSequence") ?? 0);
  const events: RunEvent[] = [{ sequence: cursor + 1, runId, conversationId,
    createdAt: "2026-09-12T00:00:00Z", type: "model.attempt", data: {
      schemaVersion: 1, requestId: runId, attemptId: conversationId, attemptNumber: 1,
      purpose: "main", retryOfAttemptId: null, retryCause: null, compactionId: null,
      parentRequestId: null, status: "started", context: {
        schemaVersion: 1, requestHash: "a".repeat(64), estimateMethod: "utf8-conservative-v1",
        estimatedInputTokens: 3, components: { system: 0, summary: 0, history: 0, currentUser: 0,
          toolResults: 0, assistant: 0, summaryInput: 0, unattributed: 0, toolDefinitions: 0, framing: 3 },
        contextLimitTokens: null, inputBudgetTokens: null, outputReserveTokens: 32,
        messageCount: 1, toolCount: 0, systemHash: "b".repeat(64), toolsHash: "c".repeat(64),
        historyMessageIds: [conversationId], summary: null, skills: [], workspace: null,
      },
    } }];
  return new Response(JSON.stringify({ events, nextAfterSequence: cursor < 2 ? cursor + 1 : null }));
};
createRoot(document.getElementById("root")!).render(<main><h1>合成資料診斷驗證</h1><RunDiagnostics runId={runId} conversationId={conversationId} /></main>);
