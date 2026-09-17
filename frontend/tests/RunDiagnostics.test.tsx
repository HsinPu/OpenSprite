import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RunDiagnostics } from "../src/features/chat/RunDiagnostics";
import type { RunEvent, RunSnapshot } from "../src/api/agentChat";

const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const event = (sequence: number): RunEvent => ({ sequence, runId, conversationId,
  type: "context.compaction.started", createdAt: "2026-08-21T08:30:00Z", data: {} });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

const snapshot = (status: RunSnapshot["status"]): RunSnapshot => ({ id: runId, conversationId, workspaceId: runId, workspaceRevision: 1, workspaceName: "test",
  workspaceRootHash: null, workspaceMountManifestHash: "", userMessageId: runId, assistantMessageId: null,
  providerId: "openai", modelId: "test", responseMode: "medium", status, completionReason: null,
  error: null, partialText: "", createdAt: event(1).createdAt, startedAt: event(1).createdAt, finishedAt: null });

it.each(["completed", "failed", "cancelled", "interrupted"] as const)("synchronizes after a running snapshot becomes %s and preserves expansion", async status => {
  const start = { ...event(1), data: { schemaVersion: 1, compactionId: runId, reason: "local_budget", fromSequence: 1, throughSequence: 4, estimatedBeforeTokens: 100, inputBudgetTokens: 200 } };
  const end = { ...event(2), type: "context.compaction.completed" as const, data: { schemaVersion: 1, compactionId: runId, throughSequence: 4, inputTokens: 100, outputTokens: 20 } };
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ events: [start], nextAfterSequence: null })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ events: [end], nextAfterSequence: null })));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<RunDiagnostics runId={runId} conversationId={conversationId} run={snapshot("running")} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(await screen.findByRole("button", { name: /壓縮作業/ }));
  view.rerender(<RunDiagnostics runId={runId} conversationId={conversationId} run={snapshot(status)} />);
  await waitFor(() => expect(screen.getByRole("button", { name: /壓縮作業/ }).textContent).toContain("完成"));
  expect(screen.getByRole("button", { name: /壓縮作業/ }).getAttribute("aria-expanded")).toBe("true");
  expect(fetcher.mock.calls[1][0]).toContain("afterSequence=1");
});

it("polls incrementally without overlapping requests and stops when closed", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ events: [event(1)], nextAfterSequence: null })))
    .mockImplementation(() => new Promise<Response>(() => {}));
  vi.stubGlobal("fetch", fetcher);
  render(<RunDiagnostics runId={runId} conversationId={conversationId} run={snapshot("running")} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  await screen.findByRole("button", { name: /壓縮作業/ });
  vi.useFakeTimers();
  // Manual refresh starts one pending request; timers must not start another.
  fireEvent.click(screen.getByRole("button", { name: "重新載入" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
  expect(fetcher).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("automatically polls after two seconds without user input", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ events: [event(1)], nextAfterSequence: null })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ events: [event(2)], nextAfterSequence: null })));
  vi.stubGlobal("fetch", fetcher);
  render(<RunDiagnostics runId={runId} conversationId={conversationId} run={snapshot("running")} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  await screen.findByRole("button", { name: /壓縮作業/ });
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2), { timeout: 3500 });
  expect(fetcher.mock.calls[1][0]).toContain("afterSequence=1");
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
});

it("does a final fetch even when the run finishes during the initial request", async () => {
  let resolve!: (value: Response) => void;
  const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ events: [], nextAfterSequence: null })));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<RunDiagnostics runId={runId} conversationId={conversationId} run={snapshot("running")} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  view.rerender(<RunDiagnostics runId={runId} conversationId={conversationId} run={snapshot("completed")} />);
  await act(async () => resolve(new Response(JSON.stringify({ events: [event(1)], nextAfterSequence: null }))));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.queryByText("正在同步最後紀錄…")).toBeNull());
});

it("explains compaction using the start receipt without inventing an after size", async () => {
  const events: RunEvent[] = [
    { ...event(1), data: { schemaVersion: 1, compactionId: runId, reason: "local_budget",
      fromSequence: 1, throughSequence: 4, estimatedBeforeTokens: 21000, inputBudgetTokens: 20480 } },
    { ...event(2), type: "context.compaction.completed", data: { schemaVersion: 1,
      compactionId: runId, throughSequence: 4, inputTokens: 100, outputTokens: 50 } },
  ];
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ events, nextAfterSequence: null }))));
  render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(await screen.findByRole("button", { name: /壓縮作業/ }));
  expect(screen.getByText("本機上下文預算管理觸發")).toBeTruthy();
  expect(screen.queryByText("超過本機輸入預算")).toBeNull();
  expect(screen.getByText("1–4")).toBeTruthy();
  expect(screen.getByText("21,000")).toBeTruthy();
  expect(screen.getByText("20,480")).toBeTruthy();
  expect(screen.getByText("此範圍是被摘要的歷史訊息；摘要請求用量不等於壓縮後上下文大小。")).toBeTruthy();
});

it.each([false, true])("preserves distinct attempts while removing only duplicate single-run errors (multiple=%s)", async multiple => {
  const failed: RunEvent = { ...event(1), type: "model.attempt", data: {
    schemaVersion: 1, requestId: runId, attemptId: conversationId, attemptNumber: 1,
    purpose: "main", retryOfAttemptId: null, retryCause: null, compactionId: null,
    parentRequestId: null, status: "failed", errorCode: "invalid_credentials",
  } };
  const events = multiple ? [failed, { ...failed, sequence: 2, data: { ...failed.data, attemptId: runId, attemptNumber: 2, retryOfAttemptId: conversationId, retryCause: "provider_context_limit" } }] : [failed];
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ events, nextAfterSequence: null }))));
  const run: RunSnapshot = { id: runId, conversationId, workspaceId: runId, workspaceRevision: 1, workspaceName: "test",
    workspaceRootHash: null, workspaceMountManifestHash: "", userMessageId: runId, assistantMessageId: null,
    providerId: "openai", modelId: "test", responseMode: "medium", status: "failed", completionReason: null,
    error: { code: "invalid_credentials", message: "", retryable: false }, partialText: "", createdAt: failed.createdAt,
    startedAt: failed.createdAt, finishedAt: failed.createdAt };
  render(<RunDiagnostics runId={runId} conversationId={conversationId} run={run} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(await screen.findByRole("button", { name: /模型請求 · 第 1 次/ }));
  expect(screen.getAllByText("模型廠家的 API 金鑰無效或已失效。")).toHaveLength(multiple ? 2 : 1);
  expect(screen.queryByText("這次執行未完成")).toBeNull();
  expect(screen.queryByText("紀錄範圍與匯出說明")).toBeNull();
});

it("resizes with keyboard, clamps the minimum and resets", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ events: [], nextAfterSequence: null }))));
  render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  const handle = await screen.findByRole("separator", { name: "調整診斷面板寬度" });
  fireEvent.keyDown(handle, { key: "ArrowLeft" });
  expect(handle.getAttribute("aria-valuenow")).toBe("570");
  for (let index = 0; index < 30; index++) fireEvent.keyDown(handle, { key: "ArrowRight" });
  expect(handle.getAttribute("aria-valuenow")).toBe("360");
  fireEvent.keyDown(handle, { key: "Home" });
  expect(handle.getAttribute("aria-valuenow")).toBe("560");
});

it("keeps the enclosing record closed when the icon is clicked", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ events: [], nextAfterSequence: null }))));
  render(<details data-testid="record"><summary>Record<RunDiagnostics runId={runId} conversationId={conversationId} /></summary></details>);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(screen.getByRole("button", { name: "更多操作" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "紀錄範圍與匯出說明" }));
  await screen.findByText("事件範圍：—–—");
  expect(screen.getByTestId("record").hasAttribute("open")).toBe(false);
  expect(screen.getByText("結果尚未確認")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "關閉說明" }));
  fireEvent.click(screen.getByRole("button", { name: "更多操作" }));
  expect(await screen.findByText("匯出已載入的診斷資料")).toBeTruthy();
});

it("retains loaded events when loading more fails, and retries the same cursor", async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ events: [event(100)], nextAfterSequence: 100 })))
    .mockRejectedValueOnce(new TypeError("network"))
    .mockResolvedValueOnce(new Response(JSON.stringify({ events: [event(101)], nextAfterSequence: null })));
  vi.stubGlobal("fetch", fetcher);
  render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(screen.getByRole("button", { name: "更多操作" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "紀錄範圍與匯出說明" }));
  await screen.findByText("事件範圍：100–100");
  fireEvent.click(screen.getByText("載入更多"));
  await screen.findByText("重新載入");
  expect(screen.getByText("事件範圍：100–100")).toBeTruthy();
  fireEvent.click(screen.getByText("重新載入"));
  await screen.findByText("事件範圍：100–101");
  expect(fetcher.mock.calls[1][0]).toBe(fetcher.mock.calls[2][0]);
});

it("loads on demand and appends history", async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("afterSequence=100")
    ? { events: [event(101)], nextAfterSequence: null }
    : { events: [event(100)], nextAfterSequence: 100 })));
  vi.stubGlobal("fetch", fetcher);
  render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(screen.getByRole("button", { name: "更多操作" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "紀錄範圍與匯出說明" }));
  await screen.findByText("事件範圍：100–100");
  fireEvent.click(screen.getByText("載入更多"));
  await screen.findByText("事件範圍：100–101");
  expect(screen.queryByText("載入更多")).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "開啟診斷明細" })));
});

it("ignores an old run's delayed response", async () => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const view = render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  view.rerender(<RunDiagnostics runId={conversationId} conversationId={conversationId} />);
  resolve(new Response(JSON.stringify({ events: [event(99)], nextAfterSequence: null })));
  await waitFor(() => expect(screen.queryByText("事件範圍：99–99")).toBeNull());
});

it("keeps technical identifiers collapsed and distinguishes missing usage from zero", async () => {
  const completed: RunEvent = { ...event(1), type: "model.attempt", data: {
    schemaVersion: 1, requestId: runId, attemptId: conversationId, attemptNumber: 1,
    purpose: "main", retryOfAttemptId: null, retryCause: null, compactionId: null,
    parentRequestId: null, status: "completed", finishReason: "final", inputTokens: null, outputTokens: 0,
  } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ events: [completed], nextAfterSequence: null }))));
  render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(await screen.findByRole("button", { name: /模型請求 · 第 1 次/ }));
  expect(screen.getByText("未回報")).toBeTruthy();
  expect(screen.getByText("0")).toBeTruthy();
  expect(screen.queryByText("attemptId")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "技術資訊" }));
  expect(await screen.findByText("attemptId")).toBeTruthy();
});

it("merges a terminal page into the expanded operation", async () => {
  const common = { schemaVersion: 1, requestId: runId, attemptId: conversationId, attemptNumber: 1,
    purpose: "main", retryOfAttemptId: null, retryCause: null, compactionId: null, parentRequestId: null };
  const start: RunEvent = { ...event(1), type: "model.attempt", data: { ...common, status: "started" } };
  const end: RunEvent = { ...event(2), type: "model.attempt", data: { ...common, status: "failed", errorCode: "invalid_credentials" } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ events: [start], nextAfterSequence: 1 })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ events: [end], nextAfterSequence: null }))));
  render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  fireEvent.click(screen.getByRole("button", { name: "開啟診斷明細" }));
  fireEvent.click(await screen.findByRole("button", { name: /模型請求 · 第 1 次/ }));
  fireEvent.click(screen.getByRole("button", { name: "載入更多" }));
  await screen.findByText("失敗");
  const row = screen.getByRole("button", { name: /模型請求 · 第 1 次/ });
  expect(row.getAttribute("aria-expanded")).toBe("true");
  expect(screen.getAllByRole("button", { name: /模型請求 · 第 1 次/ })).toHaveLength(1);
  expect(screen.queryByText("事件範圍：1–2")).toBeNull();
});
