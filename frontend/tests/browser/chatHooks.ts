import { useState } from "react";
import type { RunSnapshot } from "../../src/api/agentChat";

const run: RunSnapshot = {
  id: "11111111-1111-4111-8111-111111111111", conversationId: "22222222-2222-4222-8222-222222222222",
  workspaceId: "00000000-0000-4000-8000-000000000000", workspaceRevision: 1, workspaceName: "Default workspace",
  workspaceRootHash: null, workspaceMountManifestHash: "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
  userMessageId: "33333333-3333-4333-8333-333333333333", assistantMessageId: null,
  providerId: "openrouter", modelId: "test/original", responseMode: "medium", status: "completed",
  completionReason: "stop", error: null, partialText: "測試回覆：這是隔離的介面驗證，不會讀寫本機對話。",
  createdAt: "2026-09-08T08:00:00Z", startedAt: "2026-09-08T08:00:01Z", finishedAt: "2026-09-08T08:00:10Z",
};
const noop = () => undefined;
const asyncNoop = async () => undefined;
export function useConversationRun() {
  return { messages: [], activeRun: new URLSearchParams(window.location.search).has("empty") ? null : run, events: [], streamedText: "", loading: false,
    loadingOlderMessages: false, hasOlderMessages: false, error: null, isRecovering: false, canRecover: false, recoverConnection: async () => undefined, isSending: false, isRunning: false,
    send: async () => true, cancel: asyncNoop, loadOlderMessages: asyncNoop };
}
export function useRunInspection() {
  const [selectedRunId, setSelected] = useState<string | null>(null);
  return { selectedRunId, run: selectedRunId ? run : null, events: [], loading: false, error: null,
    inspectRun: async (id: string) => setSelected(id), retry: asyncNoop, returnToLatest: noop };
}
