import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RunEvent, RunSnapshot } from "../src/api/agentChat";
import { ExecutionContext } from "../src/features/chat/ExecutionContext";

const run: RunSnapshot = {
  id: "11111111-1111-4111-8111-111111111111",
  conversationId: "22222222-2222-4222-8222-222222222222",
  workspaceId: "00000000-0000-4000-8000-000000000000",
  workspaceRevision: 1,
  workspaceName: "Default workspace",
  workspaceRootHash: null,
  workspaceMountManifestHash: "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
  userMessageId: "33333333-3333-4333-8333-333333333333",
  assistantMessageId: null,
  providerId: "openai",
  modelId: "gpt-5.6",
  responseMode: "default",
  status: "running",
  completionReason: null,
  error: null,
  partialText: "",
  createdAt: "2026-08-29T08:00:00Z",
  startedAt: "2026-08-29T08:00:01Z",
  finishedAt: null,
};

const event: RunEvent = {
  sequence: 1,
  type: "run.started",
  runId: run.id,
  conversationId: run.conversationId,
  createdAt: run.startedAt!,
  data: {
    workspaceId: run.workspaceId,
    workspaceRevision: run.workspaceRevision,
    workspaceName: run.workspaceName,
    workspaceRootHash: run.workspaceRootHash,
    workspaceAvailability: "not_applicable",
  },
};

const compactionEvent: RunEvent = {
  ...event,
  sequence: 2,
  type: "context.compaction.started",
  data: { schemaVersion: 1, compactionId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", reason: "local_budget", fromSequence: 1, throughSequence: 10, estimatedBeforeTokens: 9000, inputBudgetTokens: 8000 },
  createdAt: "2026-08-29T08:00:02Z",
};

const modelEvent: RunEvent = {
  ...event,
  sequence: 4,
  type: "model.started",
  createdAt: "2026-08-29T08:00:04Z",
  data: { providerId: "openai", modelId: run.modelId, responseMode: "default", maxOutputTokens: 32_768 },
};

describe("execution context disclosure", () => {


  it("shows the snapshotted Workspace availability", () => {
    render(<ExecutionContext modelName="Auto Router" run={run} events={[event]} timeZone="system" defaultExpanded />);

    expect(screen.getByText("工作區狀態")).toBeTruthy();
    expect(screen.getByText("沒有資料夾")).toBeTruthy();
  });

  it("labels an output-limited completion without treating it as a failure", () => {
    const completed = {
      ...run,
      status: "completed" as const,
      assistantMessageId: "44444444-4444-4444-8444-444444444444",
      completionReason: "output_limit" as const,
      partialText: "partial",
      finishedAt: "2026-08-29T08:00:02Z",
    };
    const completedEvent: RunEvent = {
      sequence: 3,
      type: "run.completed",
      runId: run.id,
      conversationId: run.conversationId,
      createdAt: "2026-08-29T08:00:02Z",
      data: { assistantMessageId: completed.assistantMessageId, completionReason: "output_limit" },
    };

    render(<ExecutionContext modelName="Auto Router" run={completed} events={[completedEvent]} timeZone="system" defaultExpanded />);

    expect(screen.getAllByText("已達輸出上限").length).toBeGreaterThan(0);
    expect(screen.getByText("回覆達到輸出上限")).toBeTruthy();
    expect(document.querySelector(".chat-workspace__process-item--error")).toBeNull();
  });

  it("shows continuation progress and a preserved Context-limited completion", () => {
    const completed = {
      ...run,
      status: "completed" as const,
      assistantMessageId: "44444444-4444-4444-8444-444444444444",
      completionReason: "context_limit" as const,
      partialText: "partial",
      finishedAt: "2026-08-29T08:00:03Z",
    };
    const continuation: RunEvent = {
      sequence: 2,
      type: "response.continuation.started",
      runId: run.id,
      conversationId: run.conversationId,
      createdAt: "2026-08-29T08:00:02Z",
      data: { attempt: 1, maxAttempts: 2 },
    };
    const completedEvent: RunEvent = {
      sequence: 3,
      type: "run.completed",
      runId: run.id,
      conversationId: run.conversationId,
      createdAt: "2026-08-29T08:00:03Z",
      data: { assistantMessageId: completed.assistantMessageId, completionReason: "context_limit" },
    };

    render(<ExecutionContext modelName="Auto Router" run={completed} events={[continuation, completedEvent]} timeZone="system" defaultExpanded />);

    expect(screen.getByText("繼續產生回覆（1/2）")).toBeTruthy();
    expect(screen.getAllByText("對話內容空間不足").length).toBeGreaterThan(0);
    expect(screen.getByText("對話內容空間不足，保留目前回覆")).toBeTruthy();
  });

  it("shows an unlimited continuation without inventing a numeric maximum", () => {
    const continuation: RunEvent = {
      sequence: 2,
      type: "response.continuation.started",
      runId: run.id,
      conversationId: run.conversationId,
      createdAt: "2026-08-29T08:00:02Z",
      data: { attempt: 3, maxAttempts: null },
    };

    render(<ExecutionContext modelName="Auto Router" run={run} events={[continuation]} timeZone="system" defaultExpanded />);

    expect(screen.getByText("繼續產生回覆（3/∞）")).toBeTruthy();
  });

  it("starts collapsed and preserves its controlled state across Run updates", () => {
    const { rerender, container } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} expanded={false} />);
    const body = container.querySelector<HTMLElement>(".chat-workspace__context-body");

    expect(body?.hidden).toBe(true);

    rerender(<ExecutionContext modelName="GPT-5.6" run={{ ...run, partialText: "更新" }} events={[event]} timeZone="system" defaultExpanded={false} expanded={true} />);
    expect(body?.hidden).toBe(false);
  });

  it("applies a confirmed preference change", () => {
    const { rerender, container } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    const body = container.querySelector<HTMLElement>(".chat-workspace__context-body");
    expect(body?.hidden).toBe(true);

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded />);
    expect(body?.hidden).toBe(false);

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    expect(body?.hidden).toBe(true);
  });

  it("uses the existing Run start event as minimal Context preparation progress", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event]} timeZone="system" defaultExpanded />);

    expect(screen.getByText("準備對話內容")).toBeTruthy();
  });

  it("keeps each Context compaction as a distinct execution step", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event, compactionEvent, modelEvent, { ...compactionEvent, sequence: 5, data: { ...compactionEvent.data, compactionId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" }, createdAt: "2026-08-29T08:00:05Z" }]} timeZone="system" defaultExpanded />);

    expect(screen.getAllByText("整理較早的對話內容")).toHaveLength(2);
    expect(screen.getByText("請求模型 gpt-5.6")).toBeTruthy();
    expect(screen.getByText("32K")).toBeTruthy();
    expect(document.querySelector(".chat-workspace__process-item--active")?.textContent).toContain("整理較早的對話內容");
  });

  it.each([
    ["context.compaction.completed", "對話摘要已產生", "complete"],
    ["context.compaction.failed", "對話摘要產生失敗", "error"],
    ["context.compaction.cancelled", "對話摘要已取消", "unknown"],
  ] as const)("renders the explicit %s outcome", (type, label, state) => {
    const terminal: RunEvent = { ...compactionEvent, sequence: 3, type };
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[compactionEvent, terminal]} timeZone="system" defaultExpanded />);
    expect(screen.getByText(label).closest("li")?.classList.contains(`chat-workspace__process-item--${state}`)).toBe(true);
    expect(screen.queryByText("整理較早的對話內容")).toBeNull();
  });

  it("does not claim success for a missing terminal event after interruption", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={{ ...run, status: "interrupted" }} events={[compactionEvent]} timeZone="system" defaultExpanded />);
    expect(screen.getByText("對話摘要結果未知（缺少結束紀錄）").closest("li")?.classList.contains("chat-workspace__process-item--unknown")).toBe(true);
  });

  it("does not infer a legacy summary outcome from a later model request", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[{ ...compactionEvent, data: {} }, modelEvent]} timeZone="system" defaultExpanded />);
    expect(screen.getByText("對話摘要結果未知（缺少結束紀錄）").closest("li")?.classList.contains("chat-workspace__process-item--unknown")).toBe(true);
  });




  it("renders a Drawer mode without a second collapse control", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event]} timeZone="system" defaultExpanded={false} mode="drawer" />);

    expect(screen.queryByRole("button", { name: /展開本次執行|收合本次執行/ })).toBeNull();
    expect(screen.getByText("openai · gpt-5.6 · 廠商預設")).toBeTruthy();
  });

  it("opens historical inspection and restores the latest default", () => {
    const { rerender, container } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    const body = container.querySelector<HTMLElement>(".chat-workspace__context-body");
    expect(body?.hidden).toBe(true);

    rerender(<ExecutionContext modelName="GPT-5.6" run={{ ...run, status: "completed", assistantMessageId: "44444444-4444-4444-8444-444444444444", completionReason: "stop", finishedAt: "2026-08-29T08:00:02Z" }} events={[event]} timeZone="system" defaultExpanded={false} historical inspectionRunId={run.id} />);
    expect(body?.hidden).toBe(false);

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    expect(body?.hidden).toBe(true);
  });
});
