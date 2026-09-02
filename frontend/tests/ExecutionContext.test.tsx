import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunEvent, RunSnapshot } from "../src/api/agentChat";
import { ExecutionContext } from "../src/features/chat/ExecutionContext";


const run: RunSnapshot = {
  id: "11111111-1111-4111-8111-111111111111",
  conversationId: "22222222-2222-4222-8222-222222222222",
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
  data: {},
};

const compactionEvent: RunEvent = {
  ...event,
  sequence: 2,
  type: "context.compaction.started",
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

  it("shows repeated Context compactions as one execution step", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event, compactionEvent, modelEvent, { ...compactionEvent, sequence: 5, createdAt: "2026-08-29T08:00:05Z" }]} timeZone="system" defaultExpanded />);

    expect(screen.getAllByText("整理較早的對話內容")).toHaveLength(1);
    expect(screen.getByText("請求模型 gpt-5.6")).toBeTruthy();
    expect(screen.getByText("32K")).toBeTruthy();
    expect(document.querySelector(".chat-workspace__process-item--active")?.textContent).toContain("整理較早的對話內容");
  });

  it("shows the localized production calculator in tool events", () => {
    const toolStarted: RunEvent = {
      ...event,
      sequence: 2,
      type: "tool.started",
      createdAt: "2026-08-29T08:00:02Z",
      data: { callId: "calculator-call", toolName: "calculator" },
    };
    const toolCompleted: RunEvent = {
      ...event,
      sequence: 3,
      type: "tool.completed",
      createdAt: "2026-08-29T08:00:03Z",
      data: {
        callId: "calculator-call",
        toolName: "calculator",
        summary: "Calculator result: 42",
      },
    };

    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event, toolStarted, toolCompleted]} timeZone="system" defaultExpanded />);

    expect(screen.getByText("執行工具 計算器")).toBeTruthy();
    expect(screen.getByText("工具完成 計算器")).toBeTruthy();
    expect(screen.getAllByText("計算器").length).toBeGreaterThan(0);
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
